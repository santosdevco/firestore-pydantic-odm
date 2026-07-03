[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/santosdevco/firestore-pydantic-odm/publish.yml)](https://github.com/santosdevco/firestore-pydantic-odm/actions/workflows/publish.yml)
[![Release Tests](https://img.shields.io/github/actions/workflow/status/santosdevco/firestore-pydantic-odm/release.yml?branch=master&label=release%20tests&logo=google-cloud)](https://github.com/santosdevco/firestore-pydantic-odm/actions/workflows/release.yml)
[![PyPI](https://img.shields.io/pypi/v/firestore-pydantic-odm)](https://pypi.org/project/firestore-pydantic-odm/)
[![Python Versions](https://img.shields.io/pypi/pyversions/firestore-pydantic-odm)](https://pypi.org/project/firestore-pydantic-odm/)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

# Firestore Pydantic ODM

**A modern async Object-Document Mapper (ODM) for Google Cloud Firestore built with Pydantic.**

Firestore Pydantic ODM provides a fully typed, asynchronous, and Pythonic interface for Google Cloud Firestore. It combines **Pydantic's validation** with Firestore's scalability, allowing you to build applications with clean models, async CRUD operations, transactions, batch writes, subcollections, and efficient field projections.

<p align="center">

[![Documentation](https://img.shields.io/badge/📖-Documentation-2ea44f?style=for-the-badge)](https://fpo-python.santosdev.com)

</p>

> 📚 **New to Firestore Pydantic ODM?**
>
> Start with the documentation:
>
> **https://fpo-python.santosdev.com**

## Quick Links

| | |
|---|---|
| 🚀 Installation | https://fpo-python.santosdev.com/installation |
| ⚡ Quick Start | https://fpo-python.santosdev.com/quickstart |
| 📚 Concepts | https://fpo-python.santosdev.com/concepts/models |
| 🔍 Querying | https://fpo-python.santosdev.com/guides/querying |
| 📖 API Reference | https://fpo-python.santosdev.com/api/base-firestore-model |

---

## Why Firestore Pydantic ODM?

- ✅ Fully asynchronous API (`async` / `await`)
- ✅ Pydantic v1 & v2 support
- ✅ Fully typed queries and models
- ✅ CRUD operations
- ✅ Batch writes & transactions
- ✅ Subcollections
- ✅ Field projections (fetch only the fields you need)
- ✅ Firestore Emulator support
- ✅ Built for production

> **Fully Tested**
>
> Every release runs integration tests against a real Firestore instance across Python 3.9–3.12 and both Pydantic v1 and v2.
>
> **View CI results →**
> https://github.com/santosdevco/firestore-pydantic-odm/actions/workflows/release.yml

---

## Installation

```bash
pip install firestore-pydantic-odm
```

---

## Quick Start

### 1 · Define a model

```python
from firestore_pydantic_odm import BaseFirestoreModel

class User(BaseFirestoreModel):
    class Settings:
        name = "users"      # Firestore collection name

    name: str
    email: str
```

### 2 · Initialise Firestore

```python
from firestore_pydantic_odm import FirestoreDB, BaseFirestoreModel

db = FirestoreDB(project_id="my-project", emulator_host="localhost:8080")  # optional emulator
BaseFirestoreModel.initialize_db(db,[User]) # IMPORTANT the second parameter is a list with all models to initialize
```

### 3 · Async CRUD

```python
user = User(name="Alice", email="alice@example.com")
await user.save()               # CREATE

user.email = "alice@new.com"
await user.update()             # UPDATE

await user.delete()             # DELETE
```

### 3.1 · Subcollections

Declare parent relationships on the **child** model using `Settings.parent`.

```python
class Post(BaseFirestoreModel):
    class Settings:
        name = "posts"
        parent = User  # Post lives under a User

    title: str
    body: str
```

Create and query subcollection documents by passing `parent=`:

```python
user = User(name="Alice", email="alice@example.com")
await user.save()

post = Post(title="Hello", body="World")
await post.save(parent=user)  # users/{user.id}/posts/{post.id}

async for p in Post.find(parent=user):
    print(p.title)
```

You can also use the convenience accessor:

```python
async for p in user.subcollection(Post).find():
    print(p.title)
```

### 4 · Querying & Projections

```python
# Simple filter
async for u in User.find(filters=[User.name == "Alice"]):
    print(u)

# Single document
u = await User.find_one(filters=[User.email == "alice@new.com"])
```

#### Projections — selecting only the fields you need

```python
from pydantic import BaseModel

class UserProjection(BaseModel):
    name: str            # only grab the `name` field

async for u in User.find(
        filters=[User.age >= 18],
        projection=UserProjection):
    print(u.name)        # `u` is an instance of UserProjection

# Fetch a single document with a projection
u = await User.find_one(
        filters=[User.id == "abc123"],
        projection=UserProjection)
```

> **How it works:** the ODM converts `UserProjection` into a Firestore **field mask**, so the RPC fetches *only* the columns defined in that class.
> Each item yielded by `find()` (or returned by `find_one()`) is therefore of type **`UserProjection`**, giving you a clean `List[UserProjection]` with exactly the data requested.

### 5 · Batch writes

```python
from firestore_pydantic_odm import BatchOperation

ops = [
    (BatchOperation.CREATE, User(name="Bob", email="bob@example.com")),
    (BatchOperation.UPDATE, user),            # previously fetched instance
    (BatchOperation.DELETE, another_user)     # instance with `id` set
]
await User.batch_write(ops)
```

---

## Testing

The project ships with `pytest` and `pytest-asyncio` fixtures. To run the suite:

```bash
pytest
```

Set `FIRESTORE_EMULATOR_HOST=localhost:8080` to run tests against the local emulator instead of production Firestore.

---

## Contributing

1. Fork the repository
2. `git checkout -b feature/awesome`
3. Write code & tests; ensure **all tests pass**
4. Open a Pull Request describing your improvements

---

## License

Distributed under the **BSD 3-Clause License**.
See the [`LICENSE`](LICENSE) file for full text.


