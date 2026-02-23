"""
Lightweight accessor that provides Beanie-style user.subcollection(Post).find()
syntax as sugar over Post.find(parent=user).

This is NOT a Pydantic field — it's a runtime query helper.
"""

from typing import TYPE_CHECKING, Any, AsyncGenerator, List, Optional, Tuple, Type, Union

if TYPE_CHECKING:
    from .firestore_model import BaseFirestoreModel


class SubCollectionAccessor:
    """
    Bound query accessor for a subcollection under a specific parent.

    Example:
        accessor = user.subcollection(Post)
        async for post in accessor.find([Post.published == True]):
            print(post.title)
    """

    def __init__(self, parent: "BaseFirestoreModel", child_cls: Type["BaseFirestoreModel"]):
        self._parent = parent
        self._child_cls = child_cls

        # Validate that child_cls actually declares this parent type
        has_parent = (
            hasattr(child_cls, "Settings")
            and hasattr(child_cls.Settings, "parent")
            and getattr(child_cls.Settings, "parent", None) is type(parent)
        )
        if not has_parent:
            raise ValueError(
                f"{child_cls.__name__} does not declare "
                f"Settings.parent = {type(parent).__name__}"
            )

    async def add(self, doc: "BaseFirestoreModel", **kwargs) -> "BaseFirestoreModel":
        """Create a document in this subcollection."""
        return await doc.save(parent=self._parent, **kwargs)

    async def get(self, doc_id: str) -> Optional["BaseFirestoreModel"]:
        """Get a document by ID from this subcollection."""
        return await self._child_cls.get(doc_id, parent=self._parent)

    async def find(self, filters=None, **kwargs) -> AsyncGenerator:
        """Query this subcollection."""
        async for doc in self._child_cls.find(
            filters=filters, parent=self._parent, **kwargs
        ):
            yield doc

    async def find_one(self, filters=None, **kwargs):
        """Return first match from this subcollection."""
        return await self._child_cls.find_one(
            filters=filters or [], parent=self._parent, **kwargs
        )

    async def count(self, filters=None) -> int:
        """Count documents in this subcollection."""
        return await self._child_cls.count(
            filters=filters or [], parent=self._parent
        )

    async def exists(self, doc_id: str) -> bool:
        """Check if a document exists in this subcollection."""
        return await self._child_cls.exists(doc_id, parent=self._parent)

    async def delete(self, doc: "BaseFirestoreModel") -> None:
        """Delete a document from this subcollection."""
        await doc.delete()
