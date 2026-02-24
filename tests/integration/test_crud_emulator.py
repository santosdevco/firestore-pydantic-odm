"""
Integration tests — Top-level CRUD operations.

Validates create, read, update, delete, and exists against a real Firestore
backend (emulator or production) with dual-layer SDK cross-validation.
"""

import pytest
import pytest_asyncio

from .models import User

pytestmark = pytest.mark.asyncio


# ─── Create ──────────────────────────────────────────────────────────────────


async def test_save_creates_document(initialized_models, raw_client):
    """Create a user via ODM and verify via raw SDK."""
    user = User(name="Alice", email="alice@example.com", age=30)
    await user.save()

    assert user.id is not None

    # Cross-validate with raw SDK
    doc = await raw_client.collection("users").document(user.id).get()
    assert doc.exists
    data = doc.to_dict()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert data["age"] == 30


async def test_save_with_custom_id(initialized_models, raw_client):
    """Save with an explicit ID and verify it persists correctly."""
    user = User(id="custom-id-123", name="Bob", email="bob@test.com", age=25)
    await user.save()

    assert user.id == "custom-id-123"

    doc = await raw_client.collection("users").document("custom-id-123").get()
    assert doc.exists
    assert doc.to_dict()["name"] == "Bob"


async def test_save_duplicate_id_raises(initialized_models):
    """Saving with an already-existing ID should raise RuntimeError."""
    user1 = User(id="dup-id", name="First", email="first@test.com")
    await user1.save()

    user2 = User(id="dup-id", name="Second", email="second@test.com")
    with pytest.raises(RuntimeError):
        await user2.save()


async def test_save_auto_generates_id(initialized_models, raw_client):
    """Saving without an ID should auto-generate one."""
    user = User(name="Charlie", email="charlie@test.com")
    assert user.id is None

    await user.save()
    assert user.id is not None
    assert len(user.id) > 0

    doc = await raw_client.collection("users").document(user.id).get()
    assert doc.exists


# ─── Read ────────────────────────────────────────────────────────────────────


async def test_get_existing_document(initialized_models, raw_client):
    """Retrieve an existing document by ID via ODM."""
    user = User(name="Diana", email="diana@test.com", age=28)
    await user.save()

    result = await User.get(user.id)
    assert result is not None
    assert result.id == user.id
    assert result.name == "Diana"
    assert result.email == "diana@test.com"
    assert result.age == 28


async def test_get_nonexistent_returns_none(initialized_models):
    """Getting a non-existent document returns None."""
    result = await User.get("nonexistent-id-999")
    assert result is None


# ─── Update ──────────────────────────────────────────────────────────────────


async def test_update_modifies_fields(initialized_models, raw_client):
    """Update a document and verify via raw SDK."""
    user = User(name="Eve", email="eve@test.com", age=22)
    await user.save()

    user.name = "Eve Updated"
    user.age = 23
    await user.update()

    doc = await raw_client.collection("users").document(user.id).get()
    data = doc.to_dict()
    assert data["name"] == "Eve Updated"
    assert data["age"] == 23


async def test_update_partial_fields(initialized_models, raw_client):
    """Update only specific fields; others remain unchanged."""
    user = User(name="Frank", email="frank@test.com", age=35)
    await user.save()

    user.name = "Frank Updated"
    await user.update(include={"name"})

    doc = await raw_client.collection("users").document(user.id).get()
    data = doc.to_dict()
    assert data["name"] == "Frank Updated"
    assert data["email"] == "frank@test.com"  # unchanged


async def test_update_without_id_raises(initialized_models):
    """Updating a document without an ID should raise ValueError."""
    user = User(name="Ghost", email="ghost@test.com")
    with pytest.raises(ValueError):
        await user.update()


# ─── Delete ──────────────────────────────────────────────────────────────────


async def test_delete_removes_document(initialized_models, raw_client):
    """Delete a document and verify it's gone via raw SDK."""
    user = User(name="Hank", email="hank@test.com")
    await user.save()
    uid = user.id

    await user.delete()

    doc = await raw_client.collection("users").document(uid).get()
    assert not doc.exists


async def test_delete_without_id_raises(initialized_models):
    """Deleting a document without an ID should raise ValueError."""
    user = User(name="NoId", email="noid@test.com")
    with pytest.raises(ValueError):
        await user.delete()


# ─── Exists ──────────────────────────────────────────────────────────────────


async def test_exists_true(initialized_models):
    """exists() returns True for an existing document."""
    user = User(name="Ivy", email="ivy@test.com")
    await user.save()

    assert await User.exists(user.id) is True


async def test_exists_false(initialized_models):
    """exists() returns False for a non-existent document."""
    assert await User.exists("totally-fake-id") is False


# ─── Model dump ──────────────────────────────────────────────────────────────


async def test_model_dump_excludes_internal_fields(initialized_models):
    """model_dump() should not expose _parent_path or other internals."""
    user = User(name="Jack", email="jack@test.com")
    await user.save()

    result = await User.get(user.id)
    from firestore_pydantic_odm.pydantic_compat import model_dump_compat

    data = model_dump_compat(result, exclude={"id"})
    assert "_parent_path" not in data
    assert "_db" not in data


# ─── Reverse cross-validation ───────────────────────────────────────────────


async def test_sdk_write_odm_read(initialized_models, raw_client):
    """Write a document via raw SDK and read it back via ODM."""
    await raw_client.collection("users").document("sdk-user-1").set(
        {"name": "SDK User", "email": "sdk@test.com", "age": 40}
    )

    result = await User.get("sdk-user-1")
    assert result is not None
    assert result.name == "SDK User"
    assert result.email == "sdk@test.com"
    assert result.age == 40
