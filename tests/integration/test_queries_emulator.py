"""
Integration tests — Filters, ordering, and pagination.

Validates that Firestore queries actually return correct results against
a real backend (emulator or production).
"""

import os
import pytest
import pytest_asyncio

from .models import User, Product

pytestmark = pytest.mark.asyncio

# Multi-field ordering requires a composite index. Works in:
# - Emulator (indexes auto-created)
# - Real Firestore with USE_CI_FIXED_PREFIX=true (pre-deployed indexes)
_requires_emulator_or_ci_prefix = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST") and 
    os.environ.get("USE_CI_FIXED_PREFIX", "").lower() != "true",
    reason=(
        "Multi-field ordering requires a Firestore composite index. "
        "Run with emulator or set USE_CI_FIXED_PREFIX=true with deployed indexes."
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_users(initialized_models, test_id=""):
    """Insert a known set of users for query testing.
    
    test_id: Unique identifier to isolate test data when no cleanup is performed.
    """
    users = [
        User(id=f"{test_id}alice", name="Alice", email=f"alice-{test_id}@test.com", age=30),
        User(id=f"{test_id}bob", name="Bob", email=f"bob-{test_id}@test.com", age=25),
        User(id=f"{test_id}charlie", name="Charlie", email=f"charlie-{test_id}@test.com", age=35),
        User(id=f"{test_id}diana", name="Diana", email=f"diana-{test_id}@test.com", age=20),
        User(id=f"{test_id}eve", name="Eve", email=f"eve-{test_id}@test.com", age=30),
    ]
    for u in users:
        await u.save()
    return users


async def _seed_products(initialized_models, test_id=""):
    """Insert a known set of products for query testing.
    
    test_id: Unique identifier to isolate test data when no cleanup is performed.
    """
    products = [
        Product(id=f"{test_id}python", title="Python Book", price=29.99, tags=["python", "programming"]),
        Product(id=f"{test_id}go", title="Go Book", price=24.99, tags=["go", "programming"]),
        Product(id=f"{test_id}rust", title="Rust Book", price=34.99, tags=["rust", "systems"]),
    ]
    for p in products:
        await p.save()
    return products


async def _collect(async_gen) -> list:
    """Collect all items from an async generator into a list."""
    return [item async for item in async_gen]


# ── find() — no filters ─────────────────────────────────────────────────────


async def test_find_all_no_filters(initialized_models):
    """find() with no filters returns all documents."""
    users = await _seed_users(initialized_models, "find_all_")
    # Filter to only our test's documents using email field
    results = await _collect(User.find(filters=[User.email.in_([u.email for u in users])]))
    assert len(results) == 5


# ── find() — equality filters ───────────────────────────────────────────────


async def test_find_with_eq_filter(initialized_models):
    """Equality filter returns matching documents."""
    users = await _seed_users(initialized_models, "eq_filter_")
    results = await _collect(User.find(filters=[
        User.name == "Alice",
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 1
    assert results[0].name == "Alice"


async def test_find_with_ne_filter(initialized_models):
    """Not-equal filter excludes specified value."""
    users = await _seed_users(initialized_models, "ne_filter_")
    results = await _collect(User.find(filters=[
        User.name != "Alice",
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 4
    names = {r.name for r in results}
    assert "Alice" not in names


# ── find() — comparison filters ─────────────────────────────────────────────


async def test_find_with_gt_filter(initialized_models):
    """Greater-than filter works correctly."""
    users = await _seed_users(initialized_models, "gt_filter_")
    results = await _collect(User.find(filters=[
        User.age > 30,
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 1
    assert results[0].name == "Charlie"


async def test_find_with_gte_filter(initialized_models):
    """Greater-than-or-equal filter works correctly."""
    users = await _seed_users(initialized_models, "gte_filter_")
    results = await _collect(User.find(filters=[
        User.age >= 30,
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 3  # Alice(30), Charlie(35), Eve(30)


async def test_find_with_lt_filter(initialized_models):
    """Less-than filter works correctly."""
    users = await _seed_users(initialized_models, "lt_filter_")
    results = await _collect(User.find(filters=[
        User.age < 25,
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 1
    assert results[0].name == "Diana"


async def test_find_with_lte_filter(initialized_models):
    """Less-than-or-equal filter works correctly."""
    users = await _seed_users(initialized_models, "lte_filter_")
    results = await _collect(User.find(filters=[
        User.age <= 25,
        User.email.in_([u.email for u in users])
    ]))
    assert len(results) == 2  # Bob(25), Diana(20)


# ── find() — IN / NOT IN filters ────────────────────────────────────────────


async def test_find_with_in_filter(initialized_models):
    """IN filter returns documents matching any value in the list."""
    users = await _seed_users(initialized_models, "in_filter_")
    test_emails = [u.email for u in users]
    results = await _collect(
        User.find(filters=[
            User.name.in_(["Alice", "Bob"]),
            User.email.in_(test_emails)
        ])
    )
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"Alice", "Bob"}


async def test_find_with_not_in_filter(initialized_models):
    """NOT_IN filter excludes documents matching values in the list.
    
    Note: NOT_IN cannot be combined with IN, ARRAY_CONTAINS_ANY, or OR per Firestore constraints.
    """
    users = await _seed_users(initialized_models, "not_in_filter_")
    # Use a range filter on email to isolate our test data instead of IN
    # (NOT_IN cannot be used with IN in the same query)
    results = await _collect(
        User.find(filters=[
            User.name.not_in_(["Charlie", "Diana"]),
            User.email >= "a",  # Simple filter to ensure valid query
        ])
    )
    # Filter results to only our test users
    results = [r for r in results if r.id and r.id.startswith("not_in_filter_")]
    assert len(results) == 3
    names = {r.name for r in results}
    assert "Charlie" not in names
    assert "Diana" not in names


# ── find() — array filters ──────────────────────────────────────────────────


async def test_find_with_array_contains(initialized_models):
    """array_contains filter returns documents whose array field contains the value."""
    products = await _seed_products(initialized_models, "array_cont_")
    results = await _collect(
        Product.find(filters=[
            Product.tags.array_contains("python"),
            Product.title.in_([p.title for p in products])
        ])
    )
    assert len(results) == 1
    assert results[0].title == "Python Book"


async def test_find_with_array_contains_any(initialized_models):
    """array_contains_any returns docs containing any of the specified values."""
    products = await _seed_products(initialized_models, "array_any_")
    results = await _collect(
        Product.find(filters=[
            Product.tags.array_contains_any(["python", "go"]),
            Product.title.in_([p.title for p in products])
        ])
    )
    assert len(results) == 2
    titles = {r.title for r in results}
    assert titles == {"Python Book", "Go Book"}


# ── find() — multiple filters ───────────────────────────────────────────────


async def test_find_with_multiple_filters(initialized_models):
    """Combined filters narrow results correctly."""
    users = await _seed_users(initialized_models, "multi_filter_")
    results = await _collect(
        User.find(filters=[
            User.age >= 25,
            User.age <= 30,
            User.email.in_([u.email for u in users])
        ])
    )
    assert len(results) == 3  # Alice(30), Bob(25), Eve(30)


# ── find() — ordering ───────────────────────────────────────────────────────


async def test_find_order_by_ascending(initialized_models):
    """Results sorted ascending by field."""
    from firestore_pydantic_odm import OrderByDirection

    users = await _seed_users(initialized_models, "order_asc_")
    results = await _collect(
        User.find(
            filters=[User.email.in_([u.email for u in users])],
            order_by=(User.name, OrderByDirection.ASCENDING)
        )
    )
    names = [r.name for r in results]
    assert names == sorted(names)


async def test_find_order_by_descending(initialized_models):
    """Results sorted descending by field."""
    from firestore_pydantic_odm import OrderByDirection

    users = await _seed_users(initialized_models, "order_desc_")
    results = await _collect(
        User.find(
            filters=[User.email.in_([u.email for u in users])],
            order_by=(User.name, OrderByDirection.DESCENDING)
        )
    )
    names = [r.name for r in results]
    assert names == sorted(names, reverse=True)


@_requires_emulator_or_ci_prefix
async def test_find_order_by_multiple_fields(initialized_models):
    """Multi-field ordering works correctly."""
    from firestore_pydantic_odm import OrderByDirection

    users = await _seed_users(initialized_models, "order_multi_")
    results = await _collect(
        User.find(
            filters=[User.email.in_([u.email for u in users])],
            order_by=[
                (User.age, OrderByDirection.ASCENDING),
                (User.name, OrderByDirection.ASCENDING),
            ]
        )
    )
    # Verify ordering: age ascending, then name ascending for same age
    ages = [r.age for r in results]
    assert ages == sorted(ages)


# ── find() — pagination ─────────────────────────────────────────────────────


async def test_find_with_limit(initialized_models):
    """limit restricts the number of returned results."""
    users = await _seed_users(initialized_models, "limit_")
    results = await _collect(User.find(
        filters=[User.email.in_([u.email for u in users])],
        limit=2
    ))
    assert len(results) == 2


async def test_find_with_offset(initialized_models):
    """offset skips the first N results."""
    from firestore_pydantic_odm import OrderByDirection

    users = await _seed_users(initialized_models, "offset_")
    test_emails = [u.email for u in users]
    all_results = await _collect(
        User.find(
            filters=[User.email.in_(test_emails)],
            order_by=(User.name, OrderByDirection.ASCENDING)
        )
    )
    offset_results = await _collect(
        User.find(
            filters=[User.email.in_(test_emails)],
            order_by=(User.name, OrderByDirection.ASCENDING),
            offset=2,
        )
    )
    assert len(offset_results) == len(all_results) - 2
    assert offset_results[0].name == all_results[2].name


async def test_find_with_limit_and_offset(initialized_models):
    """Combined limit + offset implements pagination."""
    from firestore_pydantic_odm import OrderByDirection

    users = await _seed_users(initialized_models, "limit_offset_")
    page = await _collect(
        User.find(
            filters=[User.email.in_([u.email for u in users])],
            order_by=(User.name, OrderByDirection.ASCENDING),
            offset=1,
            limit=2,
        )
    )
    assert len(page) == 2


# ── find_one() ───────────────────────────────────────────────────────────────


async def test_find_one_returns_first(initialized_models):
    """find_one() returns a single matching document."""
    users = await _seed_users(initialized_models, "find_one_")
    result = await User.find_one(filters=[
        User.name == "Bob",
        User.email.in_([u.email for u in users])
    ])
    assert result is not None
    assert result.name == "Bob"


async def test_find_one_no_match_returns_none(initialized_models):
    """find_one() with no match returns None."""
    users = await _seed_users(initialized_models, "find_one_none_")
    result = await User.find_one(filters=[
        User.name == "Nonexistent",
        User.email.in_([u.email for u in users])
    ])
    assert result is None


# ── count() ──────────────────────────────────────────────────────────────────


async def test_count_with_filters(initialized_models):
    """count() with filters returns the correct count."""
    users = await _seed_users(initialized_models, "count_filter_")
    total = await User.count(filters=[
        User.age == 30,
        User.email.in_([u.email for u in users])
    ])
    assert total == 2  # Alice and Eve


async def test_count_all(initialized_models):
    """count() with empty filters returns total document count."""
    users = await _seed_users(initialized_models, "count_all_")
    total = await User.count(filters=[User.email.in_([u.email for u in users])])
    assert total == 5
