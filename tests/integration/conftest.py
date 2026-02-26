"""
Adaptive fixtures for integration tests.

Automatically detects whether to use the Firestore Emulator or real Firestore
based on the ``FIRESTORE_EMULATOR_HOST`` environment variable.

Emulator mode:  FIRESTORE_EMULATOR_HOST=localhost:8080  (fast, no creds)
Real mode:      FIRESTORE_EMULATOR_HOST unset/empty      (needs GCP creds)
"""

import json
import logging
import os
import warnings

import pytest
import pytest_asyncio
import httpx

from firestore_pydantic_odm import FirestoreDB, init_firestore_odm

from .models import User, Post, Comment, Product

logger = logging.getLogger(__name__)

# ── Environment detection ────────────────────────────────────────────────────

EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
DATABASE = os.environ.get("DATABASE", None) or None
CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

IS_EMULATOR = bool(EMULATOR_HOST)

# ``os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")`` returns ``""``
# (not the default) when GitHub Actions expands an unset secret to an empty
# string.  Use ``or`` so empty string still falls through to the fallback.
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or ""

if not PROJECT_ID and not IS_EMULATOR and CREDENTIALS_PATH:
    # Extract the project from the service-account JSON so the Firestore
    # client never receives an empty project string (which causes
    # RESOURCE_PROJECT_INVALID on RunQuery / streaming calls).
    try:
        with open(CREDENTIALS_PATH) as _f:
            PROJECT_ID = json.load(_f).get("project_id", "") or ""
    except Exception as _exc:
        logger.warning("Could not read project_id from SA file: %s", _exc)

if not PROJECT_ID:
    PROJECT_ID = "test-project"

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
    """Wipe all data BEFORE and AFTER each test for complete isolation."""
    # Clean BEFORE test to ensure fresh state
    await _perform_cleanup(firestore_db)
    
    yield  # ← test runs here

    # Clean AFTER test to avoid data leaks
    await _perform_cleanup(firestore_db)


async def _perform_cleanup(firestore_db):
    """Perform cleanup operation for emulator or real Firestore."""
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
        try:
            await _cleanup_real_firestore(client, TEST_COLLECTIONS)
        except Exception as exc:  # noqa: BLE001
            # A cleanup failure must NOT be re-raised: doing so turns a
            # passing test into a FAILED+ERROR pair (pytest marks the test
            # as failed when a fixture teardown raises).  Log a warning so
            # the problem is still visible without cascading into test results.
            warnings.warn(
                f"[conftest] Firestore cleanup error (data may leak between "
                f"tests): {exc}",
                stacklevel=1,
            )


async def _cleanup_real_firestore(client, collections: list):
    """Delete all documents in the specified collections (recursive, 3 levels).
    
    Uses batch operations for better performance and reliability.
    """
    for col_name in collections:
        # Collect all document references in this collection
        docs = []
        async for doc in client.collection(col_name).stream():
            docs.append(doc)
        
        # Delete in batches (Firestore limit: 500 operations per batch)
        batch_size = 500
        for i in range(0, len(docs), batch_size):
            batch = client.batch()
            batch_docs = docs[i:i + batch_size]
            
            for doc in batch_docs:
                # Delete subcollections first (up to 3 levels deep)
                await _delete_subcollections(client, doc.reference, depth=3)
                # Then delete the document itself
                batch.delete(doc.reference)
            
            await batch.commit()


async def _delete_subcollections(client, doc_ref, depth: int):
    """Recursively delete all subcollections of a document up to specified depth."""
    if depth <= 0:
        return
    
    # List all subcollections of this document
    try:
        subcols = [col async for col in doc_ref.collections()]
    except Exception:
        # If we can't list subcollections, skip
        return
    
    for subcol in subcols:
        # Get all documents in this subcollection
        subdocs = []
        async for subdoc in subcol.stream():
            subdocs.append(subdoc)
        
        # Delete in batches
        batch_size = 500
        for i in range(0, len(subdocs), batch_size):
            batch = client.batch()
            batch_docs = subdocs[i:i + batch_size]
            
            for subdoc in batch_docs:
                # Recursively delete deeper subcollections
                await _delete_subcollections(client, subdoc.reference, depth - 1)
                batch.delete(subdoc.reference)
            
            await batch.commit()


@pytest_asyncio.fixture
async def initialized_models(firestore_db):
    """Register all models with the database and return them as a dict."""
    init_firestore_odm(firestore_db, ALL_MODELS)
    return {cls.__name__: cls for cls in ALL_MODELS}
