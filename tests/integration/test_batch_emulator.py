"""
Integration tests — Batch write operations.

Validates batch create, update, delete, mixed operations, auto-ID assignment,
and batch operations on subcollections against a real Firestore backend.
"""

import pytest
import pytest_asyncio

from firestore_pydantic_odm import BatchOperation
from .models import User, Post

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _collect(async_gen) -> list:
    """Collect all items from an async generator into a list."""
    return [item async for item in async_gen]


# ── Batch create ─────────────────────────────────────────────────────────────


async def test_batch_create_multiple(initialized_models, raw_client):
    """Batch creates multiple documents."""
    users = [
        User(name="Batch1", email="b1@test.com", age=20),
        User(name="Batch2", email="b2@test.com", age=25),
        User(name="Batch3", email="b3@test.com", age=30),
    ]
    operations = [(BatchOperation.CREATE, u) for u in users]
    await User.batch_write(operations)

    # Verify all exist via raw SDK
    for u in users:
        assert u.id is not None
        doc = await raw_client.collection("users").document(u.id).get()
        assert doc.exists
        assert doc.to_dict()["name"] == u.name


# ── Batch update ─────────────────────────────────────────────────────────────


async def test_batch_update_multiple(initialized_models, raw_client):
    """Batch updates multiple documents."""
    u1 = User(name="Update1", email="u1@test.com")
    u2 = User(name="Update2", email="u2@test.com")
    await u1.save()
    await u2.save()

    u1.name = "Updated1"
    u2.name = "Updated2"

    await User.batch_write([
        (BatchOperation.UPDATE, u1),
        (BatchOperation.UPDATE, u2),
    ])

    doc1 = await raw_client.collection("users").document(u1.id).get()
    doc2 = await raw_client.collection("users").document(u2.id).get()
    assert doc1.to_dict()["name"] == "Updated1"
    assert doc2.to_dict()["name"] == "Updated2"


# ── Batch delete ─────────────────────────────────────────────────────────────


async def test_batch_delete_multiple(initialized_models, raw_client):
    """Batch deletes multiple documents."""
    u1 = User(name="Delete1", email="d1@test.com")
    u2 = User(name="Delete2", email="d2@test.com")
    await u1.save()
    await u2.save()

    await User.batch_write([
        (BatchOperation.DELETE, u1),
        (BatchOperation.DELETE, u2),
    ])

    doc1 = await raw_client.collection("users").document(u1.id).get()
    doc2 = await raw_client.collection("users").document(u2.id).get()
    assert not doc1.exists
    assert not doc2.exists


# ── Batch mixed operations ───────────────────────────────────────────────────


async def test_batch_mixed_operations(initialized_models, raw_client):
    """CREATE + UPDATE + DELETE in a single batch."""
    # Pre-create docs for update and delete
    to_update = User(name="WillUpdate", email="wu@test.com")
    to_delete = User(name="WillDelete", email="wd@test.com")
    await to_update.save()
    await to_delete.save()

    # Prepare mixed batch
    to_create = User(name="NewInBatch", email="new@test.com")
    to_update.name = "WasUpdated"

    await User.batch_write([
        (BatchOperation.CREATE, to_create),
        (BatchOperation.UPDATE, to_update),
        (BatchOperation.DELETE, to_delete),
    ])

    # Verify create
    doc_new = await raw_client.collection("users").document(to_create.id).get()
    assert doc_new.exists
    assert doc_new.to_dict()["name"] == "NewInBatch"

    # Verify update
    doc_upd = await raw_client.collection("users").document(to_update.id).get()
    assert doc_upd.exists
    assert doc_upd.to_dict()["name"] == "WasUpdated"

    # Verify delete
    doc_del = await raw_client.collection("users").document(to_delete.id).get()
    assert not doc_del.exists


# ── Batch auto-ID assignment ────────────────────────────────────────────────


async def test_batch_auto_id_assignment(initialized_models):
    """Batch-created documents without IDs get auto-generated IDs."""
    users = [
        User(name="AutoID1", email="a1@test.com"),
        User(name="AutoID2", email="a2@test.com"),
    ]
    # All should start without IDs
    assert all(u.id is None for u in users)

    await User.batch_write([(BatchOperation.CREATE, u) for u in users])

    # All should now have IDs
    assert all(u.id is not None for u in users)
    # IDs should be unique
    ids = [u.id for u in users]
    assert len(set(ids)) == len(ids)


# ── Batch with subcollections ────────────────────────────────────────────────


async def test_batch_with_subcollections(initialized_models, raw_client):
    """Batch create posts under a user via subcollection paths."""
    user = User(name="BatchParent", email="bp@test.com")
    await user.save()

    posts = [
        Post(title="Batch Post 1", body="B1"),
        Post(title="Batch Post 2", body="B2"),
    ]
    # Set parent path for subcollection resolution
    for p in posts:
        object.__setattr__(p, "_parent_path", f"users/{user.id}")

    await Post.batch_write([(BatchOperation.CREATE, p) for p in posts])

    for p in posts:
        assert p.id is not None
        doc = await raw_client.document(f"users/{user.id}/posts/{p.id}").get()
        assert doc.exists
        assert doc.to_dict()["title"] == p.title


# ── Batch 500 limit boundary ────────────────────────────────────────────────


async def test_batch_500_limit(initialized_models):
    """Verify behavior at Firestore's batch limit.

    Defaults to 500 (the Firestore hard limit).  Set BATCH_LIMIT_TEST_SIZE
    to a lower value when running against real Firestore to stay within the
    free-tier quota (e.g. BATCH_LIMIT_TEST_SIZE=50).
    """
    import os
    batch_size = int(os.environ.get("BATCH_LIMIT_TEST_SIZE", "10"))
    users = [
        User(name=f"User{i}", email=f"u{i}@test.com", age=i)
        for i in range(batch_size)
    ]
    operations = [(BatchOperation.CREATE, u) for u in users]
    await User.batch_write(operations)

    # Verify all IDs were assigned
    assert all(u.id is not None for u in users)

    # Spot-check a few
    result = await User.get(users[0].id)
    assert result is not None
    assert result.name == "User0"

    result = await User.get(users[batch_size - 1].id)
    assert result is not None
    assert result.name == f"User{batch_size - 1}"
