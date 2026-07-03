#!/usr/bin/env python3
"""
Clean up old test collections from Firestore.

This script deletes collections with the test prefix (t<run_id>_*) that are
older than a specified number of days. It uses the collection creation time
to determine age.

Environment variables:
- GOOGLE_APPLICATION_CREDENTIALS: Path to GCP service account key
- GCP_PROJECT_ID: GCP project ID
- GCP_DATABASE: (Optional) Firestore database name
- DAYS_OLD: (Optional) Delete collections older than N days (default: 30)
- DRY_RUN: (Optional) If 'true', show what would be deleted without deleting

Usage:
    python scripts/cleanup_old_test_collections.py

Example:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
    export GCP_PROJECT_ID=your-project-id
    export DAYS_OLD=60
    export DRY_RUN=false
    python scripts/cleanup_old_test_collections.py
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from google.oauth2.service_account import Credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration from environment
CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
DATABASE = os.environ.get("GCP_DATABASE") or None
DAYS_OLD = int(os.environ.get("DAYS_OLD", "30"))
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")

# Test collection prefix pattern
TEST_COLLECTION_PATTERN = re.compile(r"^t[a-f0-9]{8,}_\w+$")


async def list_collections(client):
    """List all root-level collections in the database."""
    collections = client.collections()
    return [col.id async for col in collections]


async def get_collection_age(client, collection_name):
    """
    Estimate collection age by checking the earliest document timestamp.
    
    Returns the age in days, or None if the collection is empty or has no timestamps.
    """
    try:
        # Get the first document in the collection
        docs = (
            client.collection(collection_name)
            .limit(1)
            .stream()
        )
        
        first_doc = None
        async for doc in docs:
            first_doc = doc
            break
        
        if not first_doc:
            # Empty collection - assume it's very old
            return 999
        
        # Try to get creation time from document metadata
        # Note: Firestore doesn't store creation time by default,
        # so we use the document's update_time as a proxy
        if hasattr(first_doc, 'update_time') and first_doc.update_time:
            doc_time = first_doc.update_time
            now = datetime.now(timezone.utc)
            age_days = (now - doc_time).days
            return age_days
        
        # If no timestamp, assume it's old
        return 999
    except Exception as exc:
        logger.warning(
            "Failed to get age for collection %s: %s",
            collection_name,
            exc,
        )
        return None


async def delete_collection(client, collection_name, batch_size=500):
    """Delete all documents in a collection."""
    collection_ref = client.collection(collection_name)
    
    deleted = 0
    while True:
        # Get a batch of documents
        docs = []
        async for doc in collection_ref.limit(batch_size).stream():
            docs.append(doc)
        
        if not docs:
            break
        
        # Delete batch
        batch = client.batch()
        for doc in docs:
            batch.delete(doc.reference)
        
        await batch.commit()
        deleted += len(docs)
        logger.info("  Deleted %d documents from %s", len(docs), collection_name)
    
    return deleted


async def main():
    """Main cleanup routine."""
    # Validate configuration
    if not CREDENTIALS_PATH:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS not set")
        sys.exit(1)
    
    if not PROJECT_ID:
        logger.error("GCP_PROJECT_ID not set")
        sys.exit(1)
    
    logger.info("─" * 60)
    logger.info("🧹 Starting test collection cleanup")
    logger.info("─" * 60)
    logger.info("Project ID: %s", PROJECT_ID)
    logger.info("Database: %s", DATABASE or "(default)")
    logger.info("Delete collections older than: %d days", DAYS_OLD)
    logger.info("Dry run: %s", DRY_RUN)
    logger.info("─" * 60)
    
    # Initialize Firestore client
    credentials = Credentials.from_service_account_file(CREDENTIALS_PATH)
    client = firestore.AsyncClient(
        project=PROJECT_ID,
        database=DATABASE,
        credentials=credentials,
    )
    
    try:
        # List all collections
        logger.info("📋 Listing all collections...")
        all_collections = await list_collections(client)
        logger.info("Found %d total collections", len(all_collections))
        
        # Filter test collections
        test_collections = [
            col for col in all_collections
            if TEST_COLLECTION_PATTERN.match(col)
        ]
        logger.info("Found %d test collections (matching pattern)", len(test_collections))
        
        if not test_collections:
            logger.info("✅ No test collections found - nothing to clean up")
            return
        
        # Check age and delete old ones
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_OLD)
        logger.info("Cutoff date: %s", cutoff_date.strftime("%Y-%m-%d %H:%M:%S UTC"))
        logger.info("─" * 60)
        
        total_deleted = 0
        collections_to_delete = []
        
        for col_name in test_collections:
            age_days = await get_collection_age(client, col_name)
            
            if age_days is None:
                logger.info("⏭️  %s (age unknown, skipping)", col_name)
                continue
            
            if age_days >= DAYS_OLD:
                logger.info("🗑️  %s (age: %d days)", col_name, age_days)
                collections_to_delete.append(col_name)
                
                if not DRY_RUN:
                    deleted = await delete_collection(client, col_name)
                    total_deleted += deleted
                    logger.info("    ✓ Deleted %d documents", deleted)
            else:
                logger.info("✅ %s (age: %d days, keeping)", col_name, age_days)
        
        # Summary
        logger.info("─" * 60)
        if DRY_RUN:
            logger.info(
                "🔍 DRY RUN: Would delete %d collections",
                len(collections_to_delete),
            )
            if collections_to_delete:
                logger.info("Collections that would be deleted:")
                for col in collections_to_delete:
                    logger.info("  - %s", col)
                logger.info("\nTo actually delete, set DRY_RUN=false")
        else:
            logger.info(
                "✅ Cleanup complete: Deleted %d collections (%d documents)",
                len(collections_to_delete),
                total_deleted,
            )
        
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
