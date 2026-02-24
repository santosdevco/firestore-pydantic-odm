"""
Integration tests — ODM ↔ SDK parity (cross-validation core).

Every test performs the same operation via both the ODM and the raw Firestore
SDK, then compares results to ensure the ODM is not hiding data corruption
or silent failures.
"""

import pytest
import pytest_asyncio

from firestore_pydantic_odm import BatchOperation, OrderByDirection
from firestore_pydantic_odm.pydantic_compat import model_dump_compat
from .models import User, Post

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _collect(async_gen) -> list:
    """Collect all items from an async generator into a list."""
    return [item async for item in async_gen]


# ── Create parity ───────────────────────────────────────────────────────────


async def test_create_parity(initialized_models, raw_client):
    """ODM save and SDK set produce identical documents in Firestore."""
    # ODM create
    odm_user = User(name="ODM User", email="odm@test.com", age=30)
    await odm_user.save()

    # SDK create
    sdk_data = {"name": "SDK User", "email": "sdk@test.com", "age": 30}
    await raw_client.collection("users").document("sdk-parity-1").set(sdk_data)

    # Read both via raw SDK and compare structure
    odm_doc = await raw_client.collection("users").document(odm_user.id).get()
    sdk_doc = await raw_client.collection("users").document("sdk-parity-1").get()

    assert odm_doc.exists
    assert sdk_doc.exists

    odm_data = odm_doc.to_dict()
    sdk_read = sdk_doc.to_dict()

    # Both should have the same keys and value types
    assert set(odm_data.keys()) == set(sdk_read.keys())
    assert odm_data["age"] == sdk_read["age"]


# ── Read parity ──────────────────────────────────────────────────────────────


async def test_read_parity(initialized_models, raw_client):
    """ODM get and SDK get return identical data for the same document."""
    await raw_client.collection("users").document("read-parity").set(
        {"name": "Parity", "email": "parity@test.com", "age": 42}
    )

    # Read via ODM
    odm_result = await User.get("read-parity")
    assert odm_result is not None

    # Read via SDK
    sdk_doc = await raw_client.collection("users").document("read-parity").get()
    sdk_data = sdk_doc.to_dict()

    assert odm_result.name == sdk_data["name"]
    assert odm_result.email == sdk_data["email"]
    assert odm_result.age == sdk_data["age"]


# ── Update parity ───────────────────────────────────────────────────────────


async def test_update_parity(initialized_models, raw_client):
    """ODM update and SDK update produce the same result."""
    # Create via ODM
    user = User(name="BeforeUpdate", email="up@test.com", age=10)
    await user.save()

    # Update via ODM
    user.name = "AfterUpdate"
    user.age = 20
    await user.update()

    # Read via SDK
    doc = await raw_client.collection("users").document(user.id).get()
    data = doc.to_dict()

    assert data["name"] == "AfterUpdate"
    assert data["age"] == 20
    assert data["email"] == "up@test.com"


# ── Delete parity ───────────────────────────────────────────────────────────


async def test_delete_parity(initialized_models, raw_client):
    """Both ODM and SDK delete actually remove the document."""
    # Create two docs
    user_odm = User(name="ODM Del", email="od@test.com")
    await user_odm.save()
    await raw_client.collection("users").document("sdk-del").set(
        {"name": "SDK Del", "email": "sd@test.com", "age": 0}
    )

    # Delete via ODM
    await user_odm.delete()
    # Delete via SDK
    await raw_client.collection("users").document("sdk-del").delete()

    # Both should be gone
    doc_odm = await raw_client.collection("users").document(user_odm.id).get()
    doc_sdk = await raw_client.collection("users").document("sdk-del").get()
    assert not doc_odm.exists
    assert not doc_sdk.exists


# ── Query parity ─────────────────────────────────────────────────────────────


async def test_query_parity(initialized_models, raw_client):
    """ODM find with filters and SDK where().stream() return the same results."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    # Seed data
    for i, name in enumerate(["Alice", "Bob", "Charlie"]):
        await User(name=name, email=f"{name.lower()}@test.com", age=20 + i * 5).save()

    # ODM query
    odm_results = await _collect(User.find(filters=[User.age >= 25]))
    odm_names = sorted([r.name for r in odm_results])

    # SDK query
    sdk_results = []
    query = raw_client.collection("users").where(
        filter=FieldFilter("age", ">=", 25)
    )
    async for doc in query.stream():
        sdk_results.append(doc.to_dict())
    sdk_names = sorted([d["name"] for d in sdk_results])

    assert odm_names == sdk_names


# ── Ordering parity ─────────────────────────────────────────────────────────


async def test_ordering_parity(initialized_models, raw_client):
    """ODM order_by and SDK order_by return the same order."""
    from google.cloud.firestore_v1 import query as fq

    names = ["Charlie", "Alice", "Bob"]
    for name in names:
        await User(name=name, email=f"{name.lower()}@test.com", age=25).save()

    # ODM ordering
    odm_results = await _collect(
        User.find(order_by=(User.name, OrderByDirection.ASCENDING))
    )
    odm_names = [r.name for r in odm_results]

    # SDK ordering
    sdk_names = []
    query = raw_client.collection("users").order_by("name")
    async for doc in query.stream():
        sdk_names.append(doc.to_dict()["name"])

    assert odm_names == sdk_names


# ── Subcollection path parity ───────────────────────────────────────────────


async def test_subcollection_path_parity(initialized_models, raw_client):
    """ODM path resolution matches the manual SDK path."""
    user = User(name="PathUser", email="pu@test.com")
    await user.save()

    # ODM creates at the correct subcollection path
    post = Post(title="Path Post", body="Body")
    await post.save(parent=user)

    # Expected path
    expected_path = f"users/{user.id}/posts/{post.id}"

    # Read via raw SDK using the expected path
    doc = await raw_client.document(expected_path).get()
    assert doc.exists
    assert doc.to_dict()["title"] == "Path Post"


# ── Batch parity ────────────────────────────────────────────────────────────


async def test_batch_parity(initialized_models, raw_client):
    """ODM batch and SDK batch produce the same outcome."""
    # ODM batch create
    odm_users = [
        User(name="Batch ODM 1", email="bo1@test.com"),
        User(name="Batch ODM 2", email="bo2@test.com"),
    ]
    await User.batch_write([(BatchOperation.CREATE, u) for u in odm_users])

    # SDK batch create
    batch = raw_client.batch()
    ref1 = raw_client.collection("users").document("sdk-batch-1")
    ref2 = raw_client.collection("users").document("sdk-batch-2")
    batch.set(ref1, {"name": "Batch SDK 1", "email": "bs1@test.com", "age": 0})
    batch.set(ref2, {"name": "Batch SDK 2", "email": "bs2@test.com", "age": 0})
    await batch.commit()

    # Verify all 4 exist
    for u in odm_users:
        doc = await raw_client.collection("users").document(u.id).get()
        assert doc.exists

    for sid in ["sdk-batch-1", "sdk-batch-2"]:
        doc = await raw_client.collection("users").document(sid).get()
        assert doc.exists


# ── Field alias parity ──────────────────────────────────────────────────────


async def test_field_alias_parity(initialized_models, raw_client):
    """ODM with aliases writes correct field names in Firestore.

    The ODM uses by_alias=True by default, so field names in Firestore
    should match the alias (or the field name if no alias is set).
    """
    user = User(name="AliasTest", email="alias@test.com", age=99)
    await user.save()

    doc = await raw_client.collection("users").document(user.id).get()
    data = doc.to_dict()

    # Standard fields should be stored with their names (no aliases defined)
    assert "name" in data
    assert "email" in data
    assert "age" in data
    assert data["name"] == "AliasTest"
