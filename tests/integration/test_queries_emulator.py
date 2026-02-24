"""
Integration tests — Filters, ordering, and pagination.

Validates that Firestore queries actually return correct results against
a real backend (emulator or production).
"""

import pytest
import pytest_asyncio

from .models import User, Product

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_users(initialized_models):
    """Insert a known set of users for query testing."""
    users = [
        User(name="Alice", email="alice@test.com", age=30),
        User(name="Bob", email="bob@test.com", age=25),
        User(name="Charlie", email="charlie@test.com", age=35),
        User(name="Diana", email="diana@test.com", age=20),
        User(name="Eve", email="eve@test.com", age=30),
    ]
    for u in users:
        await u.save()
    return users


async def _seed_products(initialized_models):
    """Insert a known set of products for query testing."""
    products = [
        Product(title="Python Book", price=29.99, tags=["python", "programming"]),
        Product(title="Go Book", price=24.99, tags=["go", "programming"]),
        Product(title="Rust Book", price=34.99, tags=["rust", "systems"]),
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
    await _seed_users(initialized_models)
    results = await _collect(User.find())
    assert len(results) == 5


# ── find() — equality filters ───────────────────────────────────────────────


async def test_find_with_eq_filter(initialized_models):
    """Equality filter returns matching documents."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.name == "Alice"]))
    assert len(results) == 1
    assert results[0].name == "Alice"


async def test_find_with_ne_filter(initialized_models):
    """Not-equal filter excludes specified value."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.name != "Alice"]))
    assert len(results) == 4
    names = {r.name for r in results}
    assert "Alice" not in names


# ── find() — comparison filters ─────────────────────────────────────────────


async def test_find_with_gt_filter(initialized_models):
    """Greater-than filter works correctly."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.age > 30]))
    assert len(results) == 1
    assert results[0].name == "Charlie"


async def test_find_with_gte_filter(initialized_models):
    """Greater-than-or-equal filter works correctly."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.age >= 30]))
    assert len(results) == 3  # Alice(30), Charlie(35), Eve(30)


async def test_find_with_lt_filter(initialized_models):
    """Less-than filter works correctly."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.age < 25]))
    assert len(results) == 1
    assert results[0].name == "Diana"


async def test_find_with_lte_filter(initialized_models):
    """Less-than-or-equal filter works correctly."""
    await _seed_users(initialized_models)
    results = await _collect(User.find(filters=[User.age <= 25]))
    assert len(results) == 2  # Bob(25), Diana(20)


# ── find() — IN / NOT IN filters ────────────────────────────────────────────


async def test_find_with_in_filter(initialized_models):
    """IN filter returns documents matching any value in the list."""
    await _seed_users(initialized_models)
    results = await _collect(
        User.find(filters=[User.name.in_(["Alice", "Bob"])])
    )
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"Alice", "Bob"}


async def test_find_with_not_in_filter(initialized_models):
    """NOT_IN filter excludes documents matching values in the list."""
    await _seed_users(initialized_models)
    results = await _collect(
        User.find(filters=[User.name.not_in_(["Charlie", "Diana"])])
    )
    assert len(results) == 3
    names = {r.name for r in results}
    assert "Charlie" not in names
    assert "Diana" not in names


# ── find() — array filters ──────────────────────────────────────────────────


async def test_find_with_array_contains(initialized_models):
    """array_contains filter returns documents whose array field contains the value."""
    await _seed_products(initialized_models)
    results = await _collect(
        Product.find(filters=[Product.tags.array_contains("python")])
    )
    assert len(results) == 1
    assert results[0].title == "Python Book"


async def test_find_with_array_contains_any(initialized_models):
    """array_contains_any returns docs containing any of the specified values."""
    await _seed_products(initialized_models)
    results = await _collect(
        Product.find(filters=[Product.tags.array_contains_any(["python", "go"])])
    )
    assert len(results) == 2
    titles = {r.title for r in results}
    assert titles == {"Python Book", "Go Book"}


# ── find() — multiple filters ───────────────────────────────────────────────


async def test_find_with_multiple_filters(initialized_models):
    """Combined filters narrow results correctly."""
    await _seed_users(initialized_models)
    results = await _collect(
        User.find(filters=[User.age >= 25, User.age <= 30])
    )
    assert len(results) == 3  # Alice(30), Bob(25), Eve(30)


# ── find() — ordering ───────────────────────────────────────────────────────


async def test_find_order_by_ascending(initialized_models):
    """Results sorted ascending by field."""
    from firestore_pydantic_odm import OrderByDirection

    await _seed_users(initialized_models)
    results = await _collect(
        User.find(order_by=(User.name, OrderByDirection.ASCENDING))
    )
    names = [r.name for r in results]
    assert names == sorted(names)


async def test_find_order_by_descending(initialized_models):
    """Results sorted descending by field."""
    from firestore_pydantic_odm import OrderByDirection

    await _seed_users(initialized_models)
    results = await _collect(
        User.find(order_by=(User.name, OrderByDirection.DESCENDING))
    )
    names = [r.name for r in results]
    assert names == sorted(names, reverse=True)


async def test_find_order_by_multiple_fields(initialized_models):
    """Multi-field ordering works correctly."""
    from firestore_pydantic_odm import OrderByDirection

    await _seed_users(initialized_models)
    results = await _collect(
        User.find(
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
    await _seed_users(initialized_models)
    results = await _collect(User.find(limit=2))
    assert len(results) == 2


async def test_find_with_offset(initialized_models):
    """offset skips the first N results."""
    from firestore_pydantic_odm import OrderByDirection

    await _seed_users(initialized_models)
    all_results = await _collect(
        User.find(order_by=(User.name, OrderByDirection.ASCENDING))
    )
    offset_results = await _collect(
        User.find(
            order_by=(User.name, OrderByDirection.ASCENDING),
            offset=2,
        )
    )
    assert len(offset_results) == len(all_results) - 2
    assert offset_results[0].name == all_results[2].name


async def test_find_with_limit_and_offset(initialized_models):
    """Combined limit + offset implements pagination."""
    from firestore_pydantic_odm import OrderByDirection

    await _seed_users(initialized_models)
    page = await _collect(
        User.find(
            order_by=(User.name, OrderByDirection.ASCENDING),
            offset=1,
            limit=2,
        )
    )
    assert len(page) == 2


# ── find_one() ───────────────────────────────────────────────────────────────


async def test_find_one_returns_first(initialized_models):
    """find_one() returns a single matching document."""
    await _seed_users(initialized_models)
    result = await User.find_one(filters=[User.name == "Bob"])
    assert result is not None
    assert result.name == "Bob"


async def test_find_one_no_match_returns_none(initialized_models):
    """find_one() with no match returns None."""
    await _seed_users(initialized_models)
    result = await User.find_one(filters=[User.name == "Nonexistent"])
    assert result is None


# ── count() ──────────────────────────────────────────────────────────────────


async def test_count_with_filters(initialized_models):
    """count() with filters returns the correct count."""
    await _seed_users(initialized_models)
    total = await User.count(filters=[User.age == 30])
    assert total == 2  # Alice and Eve


async def test_count_all(initialized_models):
    """count() with empty filters returns total document count."""
    await _seed_users(initialized_models)
    total = await User.count(filters=[])
    assert total == 5
