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
import uuid
import warnings

import pytest
import pytest_asyncio
import httpx

from firestore_pydantic_odm import FirestoreDB, init_firestore_odm

from .models import User, Post, Comment, Product

logger = logging.getLogger(__name__)

# ── Environment detection ────────────────────────────────────────────────────

EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
# Accept both DATABASE and GCP_DATABASE for flexibility
DATABASE = os.environ.get("DATABASE") or os.environ.get("GCP_DATABASE") or None
CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

IS_EMULATOR = bool(EMULATOR_HOST)

# ── Collection prefix for run isolation ──────────────────────────────────────

# Generate a unique prefix per test execution to isolate concurrent runs
# GitHub Actions provides GITHUB_RUN_ID; locally we generate a random ID
RUN_ID = os.environ.get("GITHUB_RUN_ID", uuid.uuid4().hex[:8])

# Only use prefix in real Firestore to avoid data collisions between runs
# Emulator doesn't need it (each run gets a fresh isolated instance)
USE_COLLECTION_PREFIX = not IS_EMULATOR
COLLECTION_PREFIX = f"t{RUN_ID}_" if USE_COLLECTION_PREFIX else ""

logger.info(
    "Test environment: %s | Prefix: %s",
    "EMULATOR" if IS_EMULATOR else "REAL FIRESTORE",
    COLLECTION_PREFIX or "(none)",
)

# Accept both GOOGLE_CLOUD_PROJECT and GCP_PROJECT_ID for flexibility
# ``os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")`` returns ``"""
# (not the default) when GitHub Actions expands an unset secret to an empty
# string.  Use ``or`` so empty string still falls through to the fallback.
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT_ID") or ""

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

# Store original collection names for restoration after tests
ORIGINAL_COLLECTION_NAMES = {
    model: model.Settings.name for model in ALL_MODELS
}

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
    """Clean test data based on environment.
    
    Emulator: Wipe all data BEFORE and AFTER each test (fast, no cost).
    Real Firestore: NO cleanup (use run-specific prefixes for isolation).
    """
    if IS_EMULATOR:
        # Clean BEFORE test to ensure fresh state
        await _perform_cleanup(firestore_db)
    
    yield  # ← test runs here

    if IS_EMULATOR:
        # Clean AFTER test to avoid data leaks
        await _perform_cleanup(firestore_db)


async def _perform_cleanup(firestore_db):
    """Perform cleanup operation for emulator only.
    
    This function should only be called when IS_EMULATOR is True.
    Real Firestore uses run-specific collection prefixes instead of cleanup.
    """
    if not IS_EMULATOR:
        logger.warning(
            "[conftest] _perform_cleanup called in real Firestore mode. "
            "This should not happen. Skipping cleanup."
        )
        return
    
    db_name = DATABASE or "(default)"
    url = (
        f"http://{EMULATOR_HOST}/emulator/v1/projects/"
        f"{PROJECT_ID}/databases/{db_name}/documents"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url)
            response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "[conftest] Emulator cleanup failed: %s. "
            "Data may leak between tests.",
            exc,
        )


@pytest_asyncio.fixture
async def initialized_models(firestore_db):
    """Register all models with the database and return them as a dict.
    
    In real Firestore mode, collection names are prefixed with the run ID
    to isolate concurrent test executions. In emulator mode, no prefix is used.
    """
    # Apply collection prefix to all models (if enabled)
    if USE_COLLECTION_PREFIX:
        for model in ALL_MODELS:
            original_name = ORIGINAL_COLLECTION_NAMES[model]
            model.Settings.name = f"{COLLECTION_PREFIX}{original_name}"
            logger.debug(
                "Prefixed collection: %s → %s",
                original_name,
                model.Settings.name,
            )
    
    # Initialize ODM with the (possibly prefixed) models
    init_firestore_odm(firestore_db, ALL_MODELS)
    
    yield {cls.__name__: cls for cls in ALL_MODELS}
    
    # Restore original collection names after test
    if USE_COLLECTION_PREFIX:
        for model in ALL_MODELS:
            model.Settings.name = ORIGINAL_COLLECTION_NAMES[model]
