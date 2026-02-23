import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, PropertyMock
from typing import Any, List, Optional, AsyncGenerator

from firestore_pydantic_odm import (
    BaseFirestoreModel,
    FirestoreDB,
    SubCollectionAccessor,
    init_firestore_odm,
    BatchOperation,
)
from google.cloud.firestore_v1.base_query import FieldFilter


# ---------------------------------------------------------------------------
# Model hierarchy for tests: User -> Post -> Comment
# ---------------------------------------------------------------------------
class User(BaseFirestoreModel):
    class Settings:
        name = "users"

    name: str
    email: str


class Post(BaseFirestoreModel):
    class Settings:
        name = "posts"
        parent = User

    title: str
    body: str
    published: bool = False


class Comment(BaseFirestoreModel):
    class Settings:
        name = "comments"
        parent = Post

    text: str
    author: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_firestore_client():
    return MagicMock()


@pytest.fixture
def firestore_db(mock_firestore_client):
    db = FirestoreDB.__new__(FirestoreDB)
    db.project_id = "test-project"
    db.database = None
    db.credentials = None
    db._emulator_host = None
    db.client = mock_firestore_client
    return db


@pytest_asyncio.fixture
async def initialized_models(firestore_db):
    """Register all models including subcollection hierarchy."""
    init_firestore_odm(firestore_db, [User, Post, Comment])
    return {"User": User, "Post": Post, "Comment": Comment}


def make_user(uid="user_123", name="Alice", email="alice@example.com"):
    """Helper to build a User with id and no _parent_path."""
    u = User(id=uid, name=name, email=email)
    return u


def make_post(pid="post_456", title="Hello", body="World", parent_user=None):
    """Helper to build a Post optionally bound to a parent user."""
    p = Post(id=pid, title=title, body=body)
    if parent_user:
        object.__setattr__(p, '_parent_path', f"users/{parent_user.id}")
    return p


# ---------------------------------------------------------------------------
# Async generator helper
# ---------------------------------------------------------------------------
async def mock_stream(docs):
    for d in docs:
        yield d


# ===========================================================================
# Test: Subcollection CRUD
# ===========================================================================
class TestSubcollectionCRUD:
    """Basic CRUD on subcollection documents."""

    @pytest.mark.asyncio
    async def test_save_subcollection_doc(self, initialized_models):
        """Post.save(parent=user) writes to users/{uid}/posts/{pid}."""
        user = make_user()
        post = Post(title="Hello", body="World")

        doc_ref_mock = MagicMock()
        doc_ref_mock.id = "auto_pid"
        doc_ref_mock.set = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock

        Post._db.client.collection.return_value = collection_ref_mock

        saved = await post.save(parent=user)

        # Verify the collection path used
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert saved.id == "auto_pid"
        assert saved._parent_path == "users/user_123"

    @pytest.mark.asyncio
    async def test_save_without_parent_raises(self, initialized_models):
        """Post.save() without parent raises RuntimeError."""
        post = Post(title="Hello", body="World")
        with pytest.raises(RuntimeError, match="requires a parent"):
            await post.save()

    @pytest.mark.asyncio
    async def test_save_with_stored_parent_path(self, initialized_models):
        """Post with _parent_path already set can save without parent arg."""
        post = Post(title="Hello", body="World")
        object.__setattr__(post, '_parent_path', "users/user_123")

        doc_ref_mock = MagicMock()
        doc_ref_mock.id = "auto_pid"
        doc_ref_mock.set = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        saved = await post.save()
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert saved._parent_path == "users/user_123"

    @pytest.mark.asyncio
    async def test_get_subcollection_doc(self, initialized_models):
        """Post.get(pid, parent=user) reads from correct path."""
        user = make_user()

        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True
        doc_snap_mock.id = "post_456"
        doc_snap_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": False,
        }

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        result = await Post.get("post_456", parent=user)

        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert result is not None
        assert result.id == "post_456"
        assert result.title == "Hello"
        assert result._parent_path == "users/user_123"

    @pytest.mark.asyncio
    async def test_find_in_subcollection(self, initialized_models):
        """Post.find(parent=user) queries the correct subcollection."""
        user = make_user()

        doc_mock = MagicMock()
        doc_mock.id = "post_1"
        doc_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": True,
        }

        collection_ref_mock = MagicMock()
        collection_ref_mock.stream = lambda: mock_stream([doc_mock])
        collection_ref_mock.where.return_value = collection_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        results = []
        async for p in Post.find(parent=user):
            results.append(p)

        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert len(results) == 1
        assert results[0]._parent_path == "users/user_123"

    @pytest.mark.asyncio
    async def test_update_subcollection_doc(self, initialized_models):
        """post.update() uses stored _parent_path."""
        post = make_post(parent_user=make_user())

        doc_ref_mock = MagicMock()
        doc_ref_mock.update = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        post.title = "Updated"
        await post.update()

        Post._db.client.collection.assert_called_with("users/user_123/posts")
        doc_ref_mock.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_with_explicit_parent(self, initialized_models):
        """post.update(parent=user) resolves path from explicit parent."""
        user = make_user()
        post = Post(id="post_456", title="Hello", body="World")

        doc_ref_mock = MagicMock()
        doc_ref_mock.update = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        await post.update(parent=user)
        Post._db.client.collection.assert_called_with("users/user_123/posts")

    @pytest.mark.asyncio
    async def test_delete_subcollection_doc(self, initialized_models):
        """post.delete() deletes from correct subcollection path."""
        post = make_post(parent_user=make_user())

        doc_ref_mock = MagicMock()
        doc_ref_mock.delete = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        await post.delete()
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        doc_ref_mock.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_count_subcollection(self, initialized_models):
        """Post.count(parent=user) counts only user's posts."""
        user = make_user()

        query_mock = MagicMock()
        count_result = MagicMock()
        count_result.value = 5
        count_get_mock = AsyncMock(return_value=[[count_result]])
        count_mock = MagicMock()
        count_mock.get = count_get_mock
        query_mock.count.return_value = count_mock

        collection_ref_mock = MagicMock()
        collection_ref_mock.where.return_value = query_mock
        # The collection ref itself should behave as the query for no-filter case
        collection_ref_mock.count = query_mock.count
        Post._db.client.collection.return_value = collection_ref_mock

        total = await Post.count(filters=[], parent=user)
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert total == 5

    @pytest.mark.asyncio
    async def test_exists_subcollection(self, initialized_models):
        """Post.exists(pid, parent=user) checks correct path."""
        user = make_user()

        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        result = await Post.exists("post_456", parent=user)
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_one_subcollection(self, initialized_models):
        """Post.find_one(parent=user) returns first match."""
        user = make_user()

        doc_mock = MagicMock()
        doc_mock.id = "post_1"
        doc_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": True,
        }

        query_mock = MagicMock()
        query_mock.stream = lambda: mock_stream([doc_mock])
        query_mock.limit.return_value = query_mock

        collection_ref_mock = MagicMock()
        collection_ref_mock.where.return_value = query_mock
        # No filters case: collection_ref itself needs stream/limit
        collection_ref_mock.stream = lambda: mock_stream([doc_mock])
        collection_ref_mock.limit.return_value = collection_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        result = await Post.find_one(
            filters=[],
            parent=user,
        )
        assert result is not None
        assert result.id == "post_1"


# ===========================================================================
# Test: Deep Nesting (User -> Post -> Comment)
# ===========================================================================
class TestDeepNesting:
    """Test 3-level nesting: User -> Post -> Comment."""

    @pytest.mark.asyncio
    async def test_save_deeply_nested(self, initialized_models):
        """comment.save(parent=post) with post under user -> 3-level path."""
        user = make_user()
        post = make_post(parent_user=user)
        comment = Comment(text="Great!", author="Bob")

        doc_ref_mock = MagicMock()
        doc_ref_mock.id = "comment_789"
        doc_ref_mock.set = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Comment._db.client.collection.return_value = collection_ref_mock

        saved = await comment.save(parent=post)

        Comment._db.client.collection.assert_called_with(
            "users/user_123/posts/post_456/comments"
        )
        assert saved.id == "comment_789"
        assert saved._parent_path == "users/user_123/posts/post_456"

    @pytest.mark.asyncio
    async def test_find_deeply_nested(self, initialized_models):
        """Comment.find(parent=post) queries correct 3-level path."""
        user = make_user()
        post = make_post(parent_user=user)

        doc_mock = MagicMock()
        doc_mock.id = "comment_1"
        doc_mock.to_dict.return_value = {"text": "Nice!", "author": "Bob"}

        collection_ref_mock = MagicMock()
        collection_ref_mock.stream = lambda: mock_stream([doc_mock])
        Comment._db.client.collection.return_value = collection_ref_mock

        results = []
        async for c in Comment.find(parent=post):
            results.append(c)

        Comment._db.client.collection.assert_called_with(
            "users/user_123/posts/post_456/comments"
        )
        assert len(results) == 1
        assert results[0]._parent_path == "users/user_123/posts/post_456"

    @pytest.mark.asyncio
    async def test_parent_path_preserved_on_get(self, initialized_models):
        """After get(), _parent_path is correctly set for deep docs."""
        user = make_user()
        post = make_post(parent_user=user)

        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True
        doc_snap_mock.id = "comment_789"
        doc_snap_mock.to_dict.return_value = {"text": "Nice!", "author": "Bob"}

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Comment._db.client.collection.return_value = collection_ref_mock

        comment = await Comment.get("comment_789", parent=post)
        assert comment._parent_path == "users/user_123/posts/post_456"


# ===========================================================================
# Test: Cascade Delete
# ===========================================================================
class TestCascadeDelete:
    """Test recursive subcollection deletion."""

    @pytest.mark.asyncio
    async def test_cascade_deletes_children(self, initialized_models):
        """user.delete(cascade=True) deletes posts and comments."""
        user = make_user()

        # Mock a post under user
        post_doc_mock = MagicMock()
        post_doc_mock.id = "post_1"
        post_doc_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": False,
        }

        # Mock a comment under post
        comment_doc_mock = MagicMock()
        comment_doc_mock.id = "comment_1"
        comment_doc_mock.to_dict.return_value = {"text": "Great!", "author": "Bob"}

        # Track all delete calls
        delete_mock = AsyncMock()
        doc_ref_mock = MagicMock()
        doc_ref_mock.delete = delete_mock

        def mock_collection(path):
            ref = MagicMock()
            ref.document.return_value = doc_ref_mock
            if path == "users/user_123/posts":
                ref.stream = lambda: mock_stream([post_doc_mock])
            elif path == "users/user_123/posts/post_1/comments":
                ref.stream = lambda: mock_stream([comment_doc_mock])
            else:
                ref.stream = lambda: mock_stream([])
            return ref

        User._db.client.collection.side_effect = mock_collection

        await user.delete(cascade=True)

        # Should have deleted: comment_1, post_1, user (3 deletes total)
        assert delete_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_no_cascade_leaves_children(self, initialized_models):
        """user.delete() without cascade only deletes the user."""
        user = make_user()

        doc_ref_mock = MagicMock()
        doc_ref_mock.delete = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        User._db.client.collection.return_value = collection_ref_mock

        await user.delete()

        doc_ref_mock.delete.assert_awaited_once()
        # Only one delete call — no cascade
        User._db.client.collection.assert_called_once_with("users")


# ===========================================================================
# Test: Collection Group Queries
# ===========================================================================
class TestCollectionGroupQuery:
    """Test collection_group_find for cross-parent queries."""

    @pytest.mark.asyncio
    async def test_find_all_posts_across_users(self, initialized_models):
        """Post.collection_group_find() returns all posts from all users."""
        doc1 = MagicMock()
        doc1.id = "post_1"
        doc1.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": True,
        }
        doc1.reference = MagicMock()
        doc1.reference.path = "users/user_1/posts/post_1"

        doc2 = MagicMock()
        doc2.id = "post_2"
        doc2.to_dict.return_value = {
            "title": "Goodbye",
            "body": "World",
            "published": False,
        }
        doc2.reference = MagicMock()
        doc2.reference.path = "users/user_2/posts/post_2"

        cg_mock = MagicMock()
        cg_mock.stream = lambda: mock_stream([doc1, doc2])
        Post._db.client.collection_group.return_value = cg_mock

        results = []
        async for p in Post.collection_group_find():
            results.append(p)

        Post._db.client.collection_group.assert_called_with("posts")
        assert len(results) == 2
        assert results[0]._parent_path == "users/user_1"
        assert results[1]._parent_path == "users/user_2"

    @pytest.mark.asyncio
    async def test_collection_group_with_filters(self, initialized_models):
        """Post.collection_group_find with filters applies FieldFilter."""
        doc_mock = MagicMock()
        doc_mock.id = "post_1"
        doc_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": True,
        }
        doc_mock.reference = MagicMock()
        doc_mock.reference.path = "users/user_1/posts/post_1"

        cg_mock = MagicMock()
        cg_mock.where.return_value = cg_mock
        cg_mock.stream = lambda: mock_stream([doc_mock])
        Post._db.client.collection_group.return_value = cg_mock

        results = []
        async for p in Post.collection_group_find(
            filters=[(str(Post.published), "==", True)]
        ):
            results.append(p)

        cg_mock.where.assert_called_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_parent_path_extracted_from_deep_ref(self, initialized_models):
        """collection_group results for comments extract correct parent path."""
        doc_mock = MagicMock()
        doc_mock.id = "comment_1"
        doc_mock.to_dict.return_value = {"text": "Hi", "author": "Bob"}
        doc_mock.reference = MagicMock()
        doc_mock.reference.path = "users/u1/posts/p1/comments/comment_1"

        cg_mock = MagicMock()
        cg_mock.stream = lambda: mock_stream([doc_mock])
        Comment._db.client.collection_group.return_value = cg_mock

        results = []
        async for c in Comment.collection_group_find():
            results.append(c)

        assert results[0]._parent_path == "users/u1/posts/p1"


# ===========================================================================
# Test: SubCollectionAccessor
# ===========================================================================
class TestSubcollectionAccessor:
    """Test the convenience accessor."""

    def test_accessor_creation(self, initialized_models):
        """user.subcollection(Post) returns an accessor."""
        user = make_user()
        accessor = user.subcollection(Post)
        assert isinstance(accessor, SubCollectionAccessor)

    def test_accessor_wrong_parent_raises(self, initialized_models):
        """user.subcollection(Comment) raises ValueError (Comment.parent=Post)."""
        user = make_user()
        with pytest.raises(ValueError, match="does not declare"):
            user.subcollection(Comment)

    @pytest.mark.asyncio
    async def test_accessor_find(self, initialized_models):
        """user.subcollection(Post).find() works like Post.find(parent=user)."""
        user = make_user()

        doc_mock = MagicMock()
        doc_mock.id = "post_1"
        doc_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": True,
        }

        collection_ref_mock = MagicMock()
        collection_ref_mock.stream = lambda: mock_stream([doc_mock])
        Post._db.client.collection.return_value = collection_ref_mock

        results = []
        async for p in user.subcollection(Post).find():
            results.append(p)

        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_accessor_add(self, initialized_models):
        """user.subcollection(Post).add(post) works like post.save(parent=user)."""
        user = make_user()
        post = Post(title="Hello", body="World")

        doc_ref_mock = MagicMock()
        doc_ref_mock.id = "auto_pid"
        doc_ref_mock.set = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        saved = await user.subcollection(Post).add(post)
        Post._db.client.collection.assert_called_with("users/user_123/posts")
        assert saved.id == "auto_pid"

    @pytest.mark.asyncio
    async def test_accessor_get(self, initialized_models):
        """user.subcollection(Post).get(pid) works like Post.get(pid, parent=user)."""
        user = make_user()

        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True
        doc_snap_mock.id = "post_456"
        doc_snap_mock.to_dict.return_value = {
            "title": "Hello",
            "body": "World",
            "published": False,
        }

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        result = await user.subcollection(Post).get("post_456")
        assert result.id == "post_456"

    @pytest.mark.asyncio
    async def test_accessor_exists(self, initialized_models):
        """user.subcollection(Post).exists(pid) checks the right path."""
        user = make_user()

        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        Post._db.client.collection.return_value = collection_ref_mock

        result = await user.subcollection(Post).exists("post_456")
        assert result is True

    @pytest.mark.asyncio
    async def test_accessor_count(self, initialized_models):
        """user.subcollection(Post).count() counts the right subcollection."""
        user = make_user()

        count_result = MagicMock()
        count_result.value = 3
        count_get_mock = AsyncMock(return_value=[[count_result]])
        count_mock = MagicMock()
        count_mock.get = count_get_mock

        collection_ref_mock = MagicMock()
        collection_ref_mock.count.return_value = count_mock
        Post._db.client.collection.return_value = collection_ref_mock

        total = await user.subcollection(Post).count()
        assert total == 3


# ===========================================================================
# Test: Backward Compatibility
# ===========================================================================
class TestBackwardCompatibility:
    """Ensure existing top-level models work unchanged."""

    @pytest.mark.asyncio
    async def test_top_level_save_unchanged(self, initialized_models):
        """User.save() without parent still works."""
        user = User(name="Alice", email="alice@example.com")

        doc_ref_mock = MagicMock()
        doc_ref_mock.id = "uid_auto"
        doc_ref_mock.set = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        User._db.client.collection.return_value = collection_ref_mock

        saved = await user.save()
        User._db.client.collection.assert_called_with("users")
        assert saved.id == "uid_auto"
        assert saved._parent_path is None

    @pytest.mark.asyncio
    async def test_top_level_get_unchanged(self, initialized_models):
        """User.get() without parent still works."""
        doc_snap_mock = MagicMock()
        doc_snap_mock.exists = True
        doc_snap_mock.id = "uid_123"
        doc_snap_mock.to_dict.return_value = {
            "name": "Alice",
            "email": "alice@example.com",
        }

        doc_ref_mock = MagicMock()
        doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        User._db.client.collection.return_value = collection_ref_mock

        user = await User.get("uid_123")
        User._db.client.collection.assert_called_with("users")
        assert user.id == "uid_123"

    @pytest.mark.asyncio
    async def test_top_level_find_unchanged(self, initialized_models):
        """User.find() without parent still works."""
        doc_mock = MagicMock()
        doc_mock.id = "uid_1"
        doc_mock.to_dict.return_value = {
            "name": "Alice",
            "email": "alice@example.com",
        }

        collection_ref_mock = MagicMock()
        collection_ref_mock.stream = lambda: mock_stream([doc_mock])
        User._db.client.collection.return_value = collection_ref_mock

        results = []
        async for u in User.find():
            results.append(u)

        User._db.client.collection.assert_called_with("users")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_top_level_delete_unchanged(self, initialized_models):
        """User.delete() without cascade still works."""
        user = User(id="uid_123", name="Alice", email="alice@example.com")

        doc_ref_mock = MagicMock()
        doc_ref_mock.delete = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        User._db.client.collection.return_value = collection_ref_mock

        await user.delete()
        doc_ref_mock.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_top_level_update_unchanged(self, initialized_models):
        """user.update() without parent still works for top-level model."""
        user = User(id="uid_123", name="Alice", email="alice@example.com")

        doc_ref_mock = MagicMock()
        doc_ref_mock.update = AsyncMock()

        collection_ref_mock = MagicMock()
        collection_ref_mock.document.return_value = doc_ref_mock
        User._db.client.collection.return_value = collection_ref_mock

        user.name = "Bob"
        await user.update()
        doc_ref_mock.update.assert_awaited_once()

    def test_model_dump_no_extra_fields(self, initialized_models):
        """model_dump() has no _parent_path or subcollection noise."""
        user = User(id="uid_123", name="Alice", email="alice@example.com")
        from firestore_pydantic_odm.pydantic_compat import model_dump_compat

        data = model_dump_compat(user, exclude={"id"})
        assert "_parent_path" not in data
        assert "subcollection" not in data
        assert data == {"name": "Alice", "email": "alice@example.com"}


# ===========================================================================
# Test: Path Resolution Helpers
# ===========================================================================
class TestPathResolution:
    """Test _get_doc_path and _get_collection_path."""

    def test_get_doc_path_top_level(self, initialized_models):
        """User._get_doc_path() returns 'users/{id}'."""
        user = make_user()
        assert user._get_doc_path() == "users/user_123"

    def test_get_doc_path_subcollection(self, initialized_models):
        """Post._get_doc_path() with _parent_path returns full path."""
        post = make_post(parent_user=make_user())
        assert post._get_doc_path() == "users/user_123/posts/post_456"

    def test_get_doc_path_no_id_raises(self, initialized_models):
        """_get_doc_path without id raises ValueError."""
        user = User(name="Alice", email="alice@example.com")
        with pytest.raises(ValueError, match="Cannot get document path without an ID"):
            user._get_doc_path()

    def test_get_child_models(self, initialized_models):
        """User._get_child_models() returns [Post]."""
        children = User._get_child_models()
        assert Post in children
        assert Comment not in children

    def test_get_child_models_post(self, initialized_models):
        """Post._get_child_models() returns [Comment]."""
        children = Post._get_child_models()
        assert Comment in children
        assert User not in children

    def test_get_child_models_leaf(self, initialized_models):
        """Comment._get_child_models() returns []."""
        children = Comment._get_child_models()
        assert children == []


# ===========================================================================
# Test: Registered Models
# ===========================================================================
class TestModelRegistry:
    """Test that _registered_models is populated by init_firestore_odm."""

    def test_registered_models(self, initialized_models):
        """All models passed to init_firestore_odm are registered."""
        assert User in BaseFirestoreModel._registered_models
        assert Post in BaseFirestoreModel._registered_models
        assert Comment in BaseFirestoreModel._registered_models
