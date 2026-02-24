"""
Shared test models for integration tests.

These models mirror a simple social-app schema:
  - User (top-level)
  - Product (top-level)
  - Post (subcollection of User)
  - Comment (subcollection of Post → nested under User)
"""

from typing import List, Optional

from firestore_pydantic_odm import BaseFirestoreModel


# ── Top-level models ─────────────────────────────────────────────────────────


class User(BaseFirestoreModel):
    class Settings:
        name = "users"

    name: str
    email: str
    age: int = 0


class Product(BaseFirestoreModel):
    class Settings:
        name = "products"

    title: str
    price: float
    tags: list = []


# ── Subcollection models ─────────────────────────────────────────────────────


class Post(BaseFirestoreModel):
    class Settings:
        name = "posts"
        parent = User

    title: str
    body: str
    published: bool = False


class Comment(BaseFirestoreModel):
    class Settings:
        name = "comments"
        parent = Post

    text: str
    author: str
