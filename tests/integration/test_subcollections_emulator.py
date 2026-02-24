"""
Integration tests — Subcollection hierarchy.

Validates subcollection CRUD, cascade delete, accessor pattern, isolation,
parent path preservation, and collection group queries against a real backend.
"""

import os

import pytest
import pytest_asyncio

from .models import User, Post, Comment

pytestmark = pytest.mark.asyncio

# Collection-group queries require an explicit Firestore composite index
# which must be deployed to the real project before the test can pass.
# When running against the local emulator the index is not required.
_needs_collection_group_index = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "collection_group_find() requires a Firestore composite index that "
        "must be deployed to the real project. Run with the emulator or "
        "create the index first (see firestore.indexes.json)."
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _collect(async_gen) -> list:
    """Collect all items from an async generator into a list."""
    return [item async for item in async_gen]


async def _create_user(name="TestUser", email="test@test.com", age=25):
    """Create and save a top-level user."""
    user = User(name=name, email=email, age=age)
    await user.save()
    return user


# ── Save subcollection documents ─────────────────────────────────────────────


async def test_save_subcollection_doc(initialized_models, raw_client):
    """Save a post under a user and verify via raw SDK."""
    user = await _create_user()
    post = Post(title="Hello World", body="My first post")
    await post.save(parent=user)

    assert post.id is not None

    # Verify via raw SDK at the correct path
    doc = await raw_client.document(f"users/{user.id}/posts/{post.id}").get()
    assert doc.exists
    data = doc.to_dict()
    assert data["title"] == "Hello World"
    assert data["body"] == "My first post"


async def test_save_deep_nesting(initialized_models, raw_client):
    """Save a comment under a post under a user (3 levels deep)."""
    user = await _create_user()
    post = Post(title="Deep Post", body="Content")
    await post.save(parent=user)

    comment = Comment(text="Great post!", author="Commenter")
    await comment.save(parent=post)

    assert comment.id is not None

    # Verify the full path via raw SDK
    full_path = f"users/{user.id}/posts/{post.id}/comments/{comment.id}"
    doc = await raw_client.document(full_path).get()
    assert doc.exists
    assert doc.to_dict()["text"] == "Great post!"


# ── Get subcollection documents ──────────────────────────────────────────────


async def test_get_subcollection_doc(initialized_models, raw_client):
    """Get a subcollection document by ID via ODM."""
    user = await _create_user()
    post = Post(title="Get Test", body="Body")
    await post.save(parent=user)

    result = await Post.get(post.id, parent=user)
    assert result is not None
    assert result.id == post.id
    assert result.title == "Get Test"


# ── Find in subcollection ───────────────────────────────────────────────────


async def test_find_in_subcollection(initialized_models):
    """find() scoped to a parent returns only that parent's children."""
    user = await _create_user()
    await Post(title="Post A", body="A").save(parent=user)
    await Post(title="Post B", body="B").save(parent=user)

    results = await _collect(Post.find(parent=user))
    assert len(results) == 2


async def test_find_with_filters_in_subcollection(initialized_models):
    """Filtered query within a subcollection scope."""
    user = await _create_user()
    await Post(title="Draft", body="draft body", published=False).save(parent=user)
    await Post(title="Published", body="pub body", published=True).save(parent=user)

    results = await _collect(
        Post.find(filters=[Post.published == True], parent=user)
    )
    assert len(results) == 1
    assert results[0].title == "Published"


# ── Update subcollection documents ───────────────────────────────────────────


async def test_update_subcollection_doc(initialized_models, raw_client):
    """Update a subcollection document and verify via raw SDK."""
    user = await _create_user()
    post = Post(title="Original", body="Original body")
    await post.save(parent=user)

    post.title = "Updated"
    await post.update()

    doc = await raw_client.document(f"users/{user.id}/posts/{post.id}").get()
    assert doc.to_dict()["title"] == "Updated"


# ── Delete subcollection documents ───────────────────────────────────────────


async def test_delete_subcollection_doc(initialized_models, raw_client):
    """Delete a subcollection document and verify it's gone."""
    user = await _create_user()
    post = Post(title="To Delete", body="Bye")
    await post.save(parent=user)
    pid = post.id

    await post.delete()

    doc = await raw_client.document(f"users/{user.id}/posts/{pid}").get()
    assert not doc.exists


# ── Cascade delete ───────────────────────────────────────────────────────────


async def test_cascade_delete(initialized_models, raw_client):
    """cascade=True deletes all subcollection children."""
    user = await _create_user()
    post1 = Post(title="Post 1", body="Body 1")
    await post1.save(parent=user)
    post2 = Post(title="Post 2", body="Body 2")
    await post2.save(parent=user)

    await user.delete(cascade=True)

    # User should be gone
    user_doc = await raw_client.document(f"users/{user.id}").get()
    assert not user_doc.exists

    # Posts should be gone
    post1_doc = await raw_client.document(f"users/{user.id}/posts/{post1.id}").get()
    assert not post1_doc.exists
    post2_doc = await raw_client.document(f"users/{user.id}/posts/{post2.id}").get()
    assert not post2_doc.exists


async def test_cascade_delete_deep(initialized_models, raw_client):
    """3-level cascade delete removes all nested documents."""
    user = await _create_user()
    post = Post(title="Deep Post", body="Body")
    await post.save(parent=user)
    comment = Comment(text="Deep comment", author="Author")
    await comment.save(parent=post)

    await user.delete(cascade=True)

    # All levels should be gone
    user_doc = await raw_client.document(f"users/{user.id}").get()
    assert not user_doc.exists
    post_doc = await raw_client.document(f"users/{user.id}/posts/{post.id}").get()
    assert not post_doc.exists
    comment_path = f"users/{user.id}/posts/{post.id}/comments/{comment.id}"
    comment_doc = await raw_client.document(comment_path).get()
    assert not comment_doc.exists


# ── Exists in subcollection ──────────────────────────────────────────────────


async def test_exists_in_subcollection(initialized_models):
    """exists() works for subcollection documents."""
    user = await _create_user()
    post = Post(title="Exists Test", body="Body")
    await post.save(parent=user)

    assert await Post.exists(post.id, parent=user) is True
    assert await Post.exists("fake-post-id", parent=user) is False


# ── Count in subcollection ───────────────────────────────────────────────────


async def test_count_in_subcollection(initialized_models):
    """count() scoped to a parent returns correct count."""
    user = await _create_user()
    await Post(title="P1", body="B1").save(parent=user)
    await Post(title="P2", body="B2").save(parent=user)
    await Post(title="P3", body="B3").save(parent=user)

    count = await Post.count(filters=[], parent=user)
    assert count == 3


# ── Subcollection accessor ───────────────────────────────────────────────────


async def test_subcollection_accessor_add(initialized_models, raw_client):
    """user.subcollection(Post).add() creates the document."""
    user = await _create_user()
    post = Post(title="Via Accessor", body="Accessor body")
    result = await user.subcollection(Post).add(post)

    assert result.id is not None
    doc = await raw_client.document(f"users/{user.id}/posts/{result.id}").get()
    assert doc.exists
    assert doc.to_dict()["title"] == "Via Accessor"


async def test_subcollection_accessor_find(initialized_models):
    """user.subcollection(Post).find() returns child documents."""
    user = await _create_user()
    await Post(title="Acc Post 1", body="B1").save(parent=user)
    await Post(title="Acc Post 2", body="B2").save(parent=user)

    results = await _collect(user.subcollection(Post).find())
    assert len(results) == 2


async def test_subcollection_accessor_get(initialized_models):
    """user.subcollection(Post).get(id) returns the document."""
    user = await _create_user()
    post = Post(title="Acc Get", body="Body")
    await post.save(parent=user)

    result = await user.subcollection(Post).get(post.id)
    assert result is not None
    assert result.title == "Acc Get"


# ── Subcollection isolation ──────────────────────────────────────────────────


async def test_subcollection_isolation(initialized_models, raw_client):
    """User A's posts are isolated from User B's posts."""
    user_a = await _create_user(name="UserA", email="a@test.com")
    user_b = await _create_user(name="UserB", email="b@test.com")

    await Post(title="A's Post", body="A body").save(parent=user_a)
    await Post(title="B's Post 1", body="B1").save(parent=user_b)
    await Post(title="B's Post 2", body="B2").save(parent=user_b)

    posts_a = await _collect(Post.find(parent=user_a))
    posts_b = await _collect(Post.find(parent=user_b))

    assert len(posts_a) == 1
    assert posts_a[0].title == "A's Post"
    assert len(posts_b) == 2


# ── Parent path preservation ────────────────────────────────────────────────


async def test_parent_path_preservation(initialized_models):
    """_parent_path is set correctly after get/find."""
    user = await _create_user()
    post = Post(title="Path Test", body="Body")
    await post.save(parent=user)

    # After get
    fetched = await Post.get(post.id, parent=user)
    assert fetched._parent_path == f"users/{user.id}"

    # After find
    found = await _collect(Post.find(parent=user))
    assert len(found) == 1
    assert found[0]._parent_path == f"users/{user.id}"


# ── Collection group queries ────────────────────────────────────────────────


@_needs_collection_group_index
async def test_collection_group_find(initialized_models):
    """collection_group_find() returns documents across all parents."""
    user_a = await _create_user(name="GroupA", email="ga@test.com")
    user_b = await _create_user(name="GroupB", email="gb@test.com")

    await Post(title="A Post", body="A", published=True).save(parent=user_a)
    await Post(title="B Post", body="B", published=True).save(parent=user_b)
    await Post(title="B Draft", body="C", published=False).save(parent=user_b)

    all_posts = await _collect(Post.collection_group_find())
    assert len(all_posts) == 3

    published = await _collect(
        Post.collection_group_find(filters=[Post.published == True])
    )
    assert len(published) == 2


# ── Reverse cross-validation ────────────────────────────────────────────────


async def test_sdk_write_subcollection_odm_read(initialized_models, raw_client):
    """Write a subcollection doc via raw SDK, read it via ODM."""
    user = await _create_user()

    # Write via raw SDK
    await raw_client.document(f"users/{user.id}/posts/sdk-post-1").set(
        {"title": "SDK Post", "body": "Written by SDK", "published": False}
    )

    result = await Post.get("sdk-post-1", parent=user)
    assert result is not None
    assert result.title == "SDK Post"
    assert result.body == "Written by SDK"
