|GitHub Workflow Status| |PyPI| |PyPI - Python Version| |License: BSD
3-Clause|

Firestore Pydantic ODM
======================

| **Firestore Pydantic ODM** is a lightweight, fully-typed
  Object-Document Mapper for **Google Cloud Firestore**.
| It combines [Pydantic]’s data-validation super-powers with Firestore’s
  scalable NoSQL store, offering async CRUD, batch writes, transactions,
  and **projections that request only the fields you need**—making
  queries faster and cheaper.

--------------

Features
--------

-  **Asynchronous CRUD:** Full support for creating, reading, updating,
   and deleting Firestore documents using ``async/await``.
-  **Validation with Pydantic:** Define your data models with automatic
   validation, ensuring data integrity before it reaches the database.
-  **Advanced Queries:** Perform searches with filters, projections
   (selecting only specific fields), and ordering.
-  **Batch Operations and Transactions:** Group multiple write
   operations and execute transactions atomically for greater efficiency
   and consistency.
-  **Emulator and Testing Support:** Easily switch to the Firestore
   emulator or plug in mocks for unit testing.
-  **Seamless Integration:** Fits smoothly into any Python project with
   minimal setup.

--------------

Installation
------------

.. code:: bash

   pip install firestore-pydantic-odm

--------------

Quick Start
-----------

1 · Define a model
~~~~~~~~~~~~~~~~~~

.. code:: python

   from firestore_pydantic_odm import BaseFirestoreModel

   class User(BaseFirestoreModel):
       class Settings:
           name = "users"      # Firestore collection name

       name: str
       email: str

2 · Initialise Firestore
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   from firestore_pydantic_odm import FirestoreDB, BaseFirestoreModel

   db = FirestoreDB(project_id="my-project", emulator_host="localhost:8080")  # optional emulator
   BaseFirestoreModel.initialize_db(db)

3 · Async CRUD
~~~~~~~~~~~~~~

.. code:: python

   user = User(name="Alice", email="alice@example.com")
   await user.save()               # CREATE

   user.email = "alice@new.com"
   await user.update()             # UPDATE

   await user.delete()             # DELETE

4 · Querying & Projections
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   # Simple filter
   async for u in User.find(filters=[User.name == "Alice"]):
       print(u)

   # Single document
   u = await User.find_one(filters=[User.email == "alice@new.com"])

Projections — selecting only the fields you need
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

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

..

   **How it works:** the ODM converts ``UserProjection`` into a
   Firestore **field mask**, so the RPC fetches *only* the columns
   defined in that class. Each item yielded by ``find()`` (or returned
   by ``find_one()``) is therefore of type **``UserProjection``**,
   giving you a clean ``List[UserProjection]`` with exactly the data
   requested.

5 · Batch writes
~~~~~~~~~~~~~~~~

.. code:: python

   from firestore_pydantic_odm import BatchOperation

   ops = [
       (BatchOperation.CREATE, User(name="Bob", email="bob@example.com")),
       (BatchOperation.UPDATE, user),            # previously fetched instance
       (BatchOperation.DELETE, another_user)     # instance with `id` set
   ]
   await User.batch_write(ops)

--------------

Testing
-------

The project ships with ``pytest`` and ``pytest-asyncio`` fixtures. To
run the suite:

.. code:: bash

   pytest

Set ``FIRESTORE_EMULATOR_HOST=localhost:8080`` to run tests against the
local emulator instead of production Firestore.

--------------

Contributing
------------

1. Fork the repository
2. ``git checkout -b feature/awesome``
3. Write code & tests; ensure **all tests pass**
4. Open a Pull Request describing your improvements

--------------

License
-------

Distributed under the **BSD 3-Clause License**. See the
```LICENSE`` <LICENSE>`__ file for full text.

.. |GitHub Workflow Status| image:: https://img.shields.io/github/actions/workflow/status/santosdevco/firestore-pydantic-odm/publish.yml
   :target: https://github.com/santosdevco/firestore-pydantic-odm/actions/workflows/publish.yml
.. |PyPI| image:: https://img.shields.io/pypi/v/firestore-pydantic-odm
   :target: https://pypi.org/project/firestore-pydantic-odm/
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/firestore-pydantic-odm
   :target: https://pypi.org/project/firestore-pydantic-odm/
.. |License: BSD 3-Clause| image:: https://img.shields.io/badge/License-BSD%203--Clause-blue.svg
   :target: https://opensource.org/licenses/BSD-3-Clause
