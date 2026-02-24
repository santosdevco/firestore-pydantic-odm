"""
Adaptive fixtures for integration tests.

Automatically detects whether to use the Firestore Emulator or real Firestore
based on the ``FIRESTORE_EMULATOR_HOST`` environment variable.

Emulator mode:  FIRESTORE_EMULATOR_HOST=localhost:8080  (fast, no creds)
Real mode:      FIRESTORE_EMULATOR_HOST unset/empty      (needs GCP creds)
"""

import os

import pytest
import pytest_asyncio
import httpx

from firestore_pydantic_odm import FirestoreDB, init_firestore_odm

from .models import User, Post, Comment, Product

# ── Environment detection ────────────────────────────────────────────────────

EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")
DATABASE = os.environ.get("DATABASE", None) or None
CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

IS_EMULATOR = bool(EMULATOR_HOST)

ALL_MODELS = [User, Post, Comment, Product]
TEST_COLLECTIONS = ["users", "products"]  # top-level only


# ── Session-scoped fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def firestore_db():
    """Create FirestoreDB pointing to emulator or real Firestore.

    Function-scoped so each test gets a fresh AsyncClient bound to the
    current event loop (avoids 'Event loop is closed' with gRPC).
    """
    if IS_EMULATOR:
        return FirestoreDB(
            project_id=PROJECT_ID,
            emulator_host=EMULATOR_HOST,
        )
    else:
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_file(CREDENTIALS_PATH)
        return FirestoreDB(
            project_id=PROJECT_ID,
            database=DATABASE,
            credentials=credentials,
        )


@pytest.fixture()
def raw_client(firestore_db):
    """Raw AsyncClient pointing to the same backend as the ODM."""
    return firestore_db.client


# ── Per-test fixtures ────────────────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def clean_firestore(firestore_db):
    """Wipe all data AFTER each test for isolation."""
    yield  # ← test runs here

    if IS_EMULATOR:
        db_name = DATABASE or "(default)"
        url = (
            f"http://{EMULATOR_HOST}/emulator/v1/projects/"
            f"{PROJECT_ID}/databases/{db_name}/documents"
        )
        async with httpx.AsyncClient() as client:
            await client.delete(url)
    else:
        client = firestore_db.client
        await _cleanup_real_firestore(client, TEST_COLLECTIONS)


async def _cleanup_real_firestore(client, collections: list):
    """Delete all documents in the specified collections (recursive, 3 levels)."""
    for col_name in collections:
        async for doc in client.collection(col_name).stream():
            # Level 2 subcollections
            subcols = doc.reference.collections()
            async for subcol in subcols:
                async for subdoc in subcol.stream():
                    # Level 3 subcollections
                    sub_subcols = subdoc.reference.collections()
                    async for sub_subcol in sub_subcols:
                        async for sub_subdoc in sub_subcol.stream():
                            await sub_subdoc.reference.delete()
                    await subdoc.reference.delete()
            await doc.reference.delete()


@pytest_asyncio.fixture
async def initialized_models(firestore_db):
    """Register all models with the database and return them as a dict."""
    init_firestore_odm(firestore_db, ALL_MODELS)
    return {cls.__name__: cls for cls in ALL_MODELS}
