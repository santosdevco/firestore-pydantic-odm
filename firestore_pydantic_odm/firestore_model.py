import logging
from typing import ClassVar, List, Tuple, Any, Optional, AsyncGenerator, Type, Union
from .pydantic_compat import (
    BaseModel,
    Field,
    get_model_fields,
    model_dump_compat,
    get_model_config,
    ConfigDict,
    PydanticVersion,
)
from .enums import BatchOperation, OrderByDirection, FirestoreOperators
from .firestore_client import FirestoreDB
from .firestore_fields import  FirestoreField
from google.cloud.firestore_v1 import AsyncClient
from google.cloud.firestore_v1.field_path import FieldPath
from google.cloud.firestore_v1.base_query import FieldFilter


# Alias for the first element in order-by tuple
FieldType = Union[str, FirestoreField]
# Alias for field ordering tuples
FieldOrderType = Tuple[FieldType, OrderByDirection]

logger = logging.getLogger(__name__)

class BaseFirestoreModel(BaseModel ):
    """
    Base ODM for Firestore with asynchronous operations.
    """

    # --------------------------------------------------------------------------
    # Default field (document ID)
    # --------------------------------------------------------------------------
    id: Optional[str] = Field(default=None)

    # --------------------------------------------------------------------------
    # Class attribute for injected FirestoreDB instance
    # --------------------------------------------------------------------------
    _db: ClassVar[Optional["FirestoreDB"]] = None  # Injected externally
    _parent_path: ClassVar[Optional[str]] = None  # Stores parent doc path for subcollections
    _registered_models: ClassVar[list] = []  # Populated by init_firestore_odm

    # --------------------------------------------------------------------------
    # Collection definition
    # --------------------------------------------------------------------------
    class Settings:
        name: str = "BaseCollection"  # Override in subclasses

    # --------------------------------------------------------------------------
    # Pydantic configuration
    # --------------------------------------------------------------------------
    if PydanticVersion >= 2:
        model_config = ConfigDict(**get_model_config())
    else:
        class Config:
            allow_population_by_field_name = True
            allow_population_by_alias = True
    @classmethod
    def initialize_fields(cls) -> None:

        # 1) Obtenemos el diccionario de campos según la versión:
        fields_dict = get_model_fields(cls)
       
        for field_name, field_info in fields_dict.items():
            # field_info.alias funciona en V1 y V2 (pydantic.v1 expone alias)
            alias = (
                FieldPath.document_id() if field_name == "id"
                else (field_info.alias or field_name)  # type: ignore[attr-defined]
            )
            setattr(cls, field_name, FirestoreField(alias))
    # --------------------------------------------------------------------------
    # Database initialization methods (injection)
    # --------------------------------------------------------------------------
    @classmethod
    def initialize_db(cls, db: "FirestoreDB"):
        """
        Inject the FirestoreDB instance to be used for all operations.
        """
        cls._db = db

    @property
    def collection_name(self) -> str:
        """
        Return the Firestore collection name for this model.
        """
        if hasattr(self, "Settings") and hasattr(self.Settings, "name"):
            return self.Settings.name
        return self.__class__.__name__

    @classmethod
    def get_collection_name(cls) -> str:
        """
        Class-level method to get the collection name.
        """
        if hasattr(cls, "Settings") and hasattr(cls.Settings, "name"):
            return cls.Settings.name
        return cls.__name__

    # --------------------------------------------------------------------------
    # Path resolution for subcollections
    # --------------------------------------------------------------------------
    def _get_doc_path(self) -> str:
        """
        Return the full Firestore document path for this instance.
        E.g. 'users/uid_123' or 'users/uid_123/posts/pid_456'
        """
        if not self.id:
            raise ValueError("Cannot get document path without an ID.")

        collection_path = self._get_collection_path()
        return f"{collection_path}/{self.id}"

    def _get_collection_path(self, parent: Optional["BaseFirestoreModel"] = None) -> str:
        """
        Resolve the full collection path, considering parent hierarchy.
        """
        has_parent_setting = (
            hasattr(self, "Settings")
            and hasattr(self.Settings, "parent")
            and getattr(self.Settings, "parent", None) is not None
        )

        if has_parent_setting:
            if parent is not None:
                parent_doc_path = parent._get_doc_path()
            elif self._parent_path is not None:
                parent_doc_path = self._parent_path
            else:
                raise RuntimeError(
                    f"{self.__class__.__name__} has Settings.parent = "
                    f"{self.Settings.parent.__name__}, but no parent instance "
                    f"was provided and no _parent_path is stored."
                )
            return f"{parent_doc_path}/{self.get_collection_name()}"
        else:
            return self.get_collection_name()

    @classmethod
    def _resolve_collection_ref(
        cls,
        db_client: "AsyncClient",
        parent: Optional["BaseFirestoreModel"] = None,
        parent_path: Optional[str] = None,
    ):
        """
        Resolve the Firestore collection reference.

        For top-level models -> db.collection("users")
        For subcollection models -> db.collection("users/uid/posts")

        Returns (collection_ref, resolved_parent_path).
        """
        has_parent_setting = (
            hasattr(cls, "Settings")
            and hasattr(cls.Settings, "parent")
            and getattr(cls.Settings, "parent", None) is not None
        )

        if has_parent_setting:
            if parent is not None:
                parent_doc_path = parent._get_doc_path()
            elif parent_path is not None:
                parent_doc_path = parent_path
            else:
                raise RuntimeError(
                    f"{cls.__name__} requires a parent ({cls.Settings.parent.__name__}) "
                    f"but none was provided."
                )
            full_path = f"{parent_doc_path}/{cls.get_collection_name()}"
            return db_client.collection(full_path), parent_doc_path
        else:
            return db_client.collection(cls.get_collection_name()), None

    @classmethod
    def _get_child_models(cls) -> list:
        """
        Return all registered model classes that declare this class as parent.
        """
        return [
            model for model in cls._registered_models
            if (
                hasattr(model, "Settings")
                and hasattr(model.Settings, "parent")
                and getattr(model.Settings, "parent", None) is cls
            )
        ]

    async def _cascade_delete(self, db_client: "AsyncClient") -> None:
        """
        Recursively delete all subcollection documents under this document.
        """
        child_models = self._get_child_models()
        doc_path = self._get_doc_path()

        for child_cls in child_models:
            child_collection_path = f"{doc_path}/{child_cls.get_collection_name()}"
            child_ref = db_client.collection(child_collection_path)

            async for child_doc in child_ref.stream():
                child_instance = child_cls(**child_doc.to_dict(), id=child_doc.id)
                object.__setattr__(child_instance, '_parent_path', doc_path)
                # Recurse into grandchildren
                await child_instance._cascade_delete(db_client)
                await child_ref.document(child_doc.id).delete()

    def subcollection(self, child_cls: Type["BaseFirestoreModel"]):
        """
        Convenience accessor for subcollection queries.
        Returns a SubCollectionAccessor bound to this parent instance.

        Usage:
            async for post in user.subcollection(Post).find():
                print(post.title)
        """
        from .subcollection_accessor import SubCollectionAccessor
        return SubCollectionAccessor(parent=self, child_cls=child_cls)

    # --------------------------------------------------------------------------
    # CRUD operations: create/update/delete
    # --------------------------------------------------------------------------
    async def save(self, parent: Optional["BaseFirestoreModel"] = None, exclude_none=True, by_alias=True, exclude_unset=True) -> "BaseFirestoreModel":
        """
        Create the document in Firestore asynchronously.
        """
        if not self._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = self._db.client

        data_to_save = model_dump_compat(
            self,
            exclude={"id"},
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            by_alias=by_alias,
        )
        collection_ref, resolved_parent_path = self._resolve_collection_ref(
            db_client, parent=parent, parent_path=self._parent_path
        )
        if resolved_parent_path is not None:
            object.__setattr__(self, '_parent_path', resolved_parent_path)

        if not self.id:
            doc_ref = collection_ref.document()
            self.id = doc_ref.id
        else:
            doc_ref = collection_ref.document(self.id)
            if (await doc_ref.get()).exists:
                raise RuntimeError("Error creating object: provided ID already exists.")

        await doc_ref.set(data_to_save)
        return self

    async def update(
        self,
        parent: Optional["BaseFirestoreModel"] = None,
        include: Optional[set] = None,
        exclude_none=True,
        by_alias=True,
        exclude_unset=True,
    ) -> "BaseFirestoreModel":
        """
        Update fields on an existing Firestore document.
        """
        if not self._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = self._db.client

        if not self.id:
            raise ValueError("Cannot update a document without an ID.")

        collection_ref, _ = self._resolve_collection_ref(
            db_client, parent=parent, parent_path=self._parent_path
        )
        doc_ref = collection_ref.document(self.id)

        if include:
            updates = model_dump_compat(
                self,
                exclude={"id"},
                include=include,
                exclude_unset=exclude_unset,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
        else:
            updates = model_dump_compat(
                self,
                exclude={"id"},
                exclude_unset=exclude_unset,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )

        logger.debug(f"Update: {self.collection_name} - id={self.id}, updates={updates}")
        if updates:
            await doc_ref.update(updates)
        return self

    async def delete(self, cascade: bool = False) -> None:
        """
        Delete the document from Firestore.
        If cascade=True, recursively deletes all subcollection documents first.
        """
        if not self._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = self._db.client

        if not self.id:
            raise ValueError("Cannot delete a document without an ID.")

        collection_ref, _ = self._resolve_collection_ref(
            db_client, parent_path=self._parent_path
        )
        doc_ref = collection_ref.document(self.id)

        if cascade:
            await self._cascade_delete(db_client)

        await doc_ref.delete()

    # --------------------------------------------------------------------------
    # Get a document by ID
    # --------------------------------------------------------------------------
    @classmethod
    async def get(
        cls,
        doc_id: str,
        parent: Optional["BaseFirestoreModel"] = None,
    ) -> Optional["BaseFirestoreModel"]:
        """
        Retrieve a document by its ID.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        collection_ref, resolved_parent_path = cls._resolve_collection_ref(
            db_client, parent=parent
        )
        doc_ref = collection_ref.document(doc_id)
        doc_snap = await doc_ref.get()

        if doc_snap.exists:
            data = doc_snap.to_dict()
            data["id"] = doc_snap.id
            instance = cls(**data)
            object.__setattr__(instance, '_parent_path', resolved_parent_path)
            return instance
        return None

    # --------------------------------------------------------------------------
    # Check if a document exists by ID
    # --------------------------------------------------------------------------
    @classmethod
    async def exists(
        cls,
        doc_id: str,
        parent: Optional["BaseFirestoreModel"] = None,
    ) -> bool:
        """
        Return True if a document with the given ID exists in Firestore.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        collection_ref, _ = cls._resolve_collection_ref(db_client, parent=parent)
        doc_ref = collection_ref.document(doc_id)
        doc_snap = await doc_ref.get()
        return doc_snap.exists

    # --------------------------------------------------------------------------
    # Count documents
    # --------------------------------------------------------------------------
    @classmethod
    async def count(
        cls,
        filters: List[Tuple[str, str, Any]],
        parent: Optional["BaseFirestoreModel"] = None,
    ) -> int:
        """
        Return the number of documents matching the given filters.
        If the SDK does not support .count(), a manual approach is used.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        query, _ = cls._build_query(db_client, filters=filters, parent=parent)
        try:
            count_snapshot = await query.count().get()
            return count_snapshot[0][0].value
        except AttributeError:
            logger.warning("Firestore: Performing count by fetching all items with empty select")
            docs = await query.select([]).get()
            return len(docs)

    # --------------------------------------------------------------------------
    # Find (asynchronous generator)
    # --------------------------------------------------------------------------
    @classmethod
    async def find(
        cls,
        filters: List[Tuple[FieldType, FirestoreOperators, Any]] = None,
        parent: Optional["BaseFirestoreModel"] = None,
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[
            Union[List[Union[FieldType, FieldOrderType]], Union[FieldType, FieldOrderType]]
        ] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> AsyncGenerator[Union["BaseFirestoreModel", Type[BaseModel]], None]:
        """
        Asynchronously search for documents matching filters and yield instances.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        filters = filters or []
        query, resolved_parent_path = cls._build_query(
            db_client, filters=filters, projection=projection, parent=parent
        )

        # Ordering
        if order_by:
            if not isinstance(order_by, list):
                order_by = [order_by]
            for order_by_field in order_by:
                if isinstance(order_by_field, tuple):
                    field, direction = order_by_field
                    query = query.order_by(str(field), direction=str(direction))
                else:
                    query = query.order_by(str(order_by_field))

        # Pagination
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        docs = query.stream()
        constructor = cls if projection is None else projection
        async for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            instance = constructor(**data)
            if resolved_parent_path:
                object.__setattr__(instance, '_parent_path', resolved_parent_path)
            yield instance

    # --------------------------------------------------------------------------
    # Find one (first matching document)
    # --------------------------------------------------------------------------
    @classmethod
    async def find_one(
        cls,
        filters: List[Tuple[str, str, Any]],
        parent: Optional["BaseFirestoreModel"] = None,
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[Union[FieldType, FieldOrderType]] = None,
    ) -> Optional["BaseFirestoreModel"]:
        """
        Return the first document matching filters, or None if no match.
        """
        async for obj in cls.find(
            filters=filters, parent=parent, projection=projection, order_by=order_by, limit=1
        ):
            return obj
        return None

    # --------------------------------------------------------------------------
    # Internal query builder
    # --------------------------------------------------------------------------
    @classmethod
    def _build_query(
        cls,
        db_client: AsyncClient,
        filters: List[Tuple[str, str, Any]],
        projection: Optional[Type[BaseModel]] = None,
        parent: Optional["BaseFirestoreModel"] = None,
    ):
        """
        Build a Firestore query applying filters and optional projection.
        Returns (query, resolved_parent_path).
        """
        collection_ref, resolved_parent_path = cls._resolve_collection_ref(
            db_client, parent=parent
        )
        query = collection_ref

        # Apply filters
        for (field_name, op, value) in filters:
            query = query.where(filter=FieldFilter(field_name, op, value))

        # Projection
        if projection:
            # Pydantic v2 → los campos están en projection.model_fields
            if hasattr(projection, "model_fields"):
                select_fields = [model_field.alias or name for name, model_field in projection.model_fields.items()]

            # Pydantic v1 → los campos están en projection.__fields__
            else:
                select_fields = [model_field.alias or name for name, model_field in projection.__fields__.items()]
            query = query.select(select_fields)
    

        return query, resolved_parent_path

    # --------------------------------------------------------------------------
    # Collection group queries (cross-parent)
    # --------------------------------------------------------------------------
    @classmethod
    async def collection_group_find(
        cls,
        filters: List[Tuple[FieldType, FirestoreOperators, Any]] = None,
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[
            Union[List[Union[FieldType, FieldOrderType]], Union[FieldType, FieldOrderType]]
        ] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> AsyncGenerator[Union["BaseFirestoreModel", Type[BaseModel]], None]:
        """
        Query across ALL subcollections with this name, regardless of parent.
        Uses Firestore's collection_group() API.

        Example: Post.collection_group_find([Post.published == True])
        -> returns posts from ALL users
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        filters = filters or []
        query = db_client.collection_group(cls.get_collection_name())

        for (field_name, op, value) in filters:
            query = query.where(filter=FieldFilter(field_name, op, value))

        # Ordering
        if order_by:
            if not isinstance(order_by, list):
                order_by = [order_by]
            for order_by_field in order_by:
                if isinstance(order_by_field, tuple):
                    field, direction = order_by_field
                    query = query.order_by(str(field), direction=str(direction))
                else:
                    query = query.order_by(str(order_by_field))

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        constructor = cls if projection is None else projection
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            instance = constructor(**data)
            # Extract parent path from the document reference
            ref_path = doc.reference.path  # e.g. "users/uid/posts/pid"
            parts = ref_path.rsplit("/", 2)  # ["users/uid", "posts", "pid"]
            if len(parts) >= 3:
                object.__setattr__(instance, '_parent_path', parts[0])
            yield instance

    # --------------------------------------------------------------------------
    # Batch operations
    # --------------------------------------------------------------------------
    @classmethod
    async def batch_write(cls, operations: List[Tuple["BatchOperation", "BaseFirestoreModel"]]):
        """
        Execute atomic batch operations (create, update, delete).
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        batch = db_client.batch()

        for op, model_instance in operations:
            collection_ref, resolved_parent_path = model_instance._resolve_collection_ref(
                db_client, parent_path=model_instance._parent_path
            )

            if not model_instance.id and op != BatchOperation.CREATE:
                raise ValueError(f"Cannot {op} without an ID assigned on {model_instance}.")

            doc_ref = (
                collection_ref.document(model_instance.id)
                if model_instance.id
                else collection_ref.document()
            )

            if op == BatchOperation.CREATE:
                if not model_instance.id:
                    model_instance.id = doc_ref.id
                data_to_save = model_dump_compat(
                    model_instance, exclude={"id"}, by_alias=True, exclude_none=True
                )
                batch.set(doc_ref, data_to_save)

            elif op == BatchOperation.UPDATE:
                data_to_update = model_dump_compat(
                    model_instance, exclude={"id"}, by_alias=True, exclude_none=True
                )
                batch.update(doc_ref, data_to_update)

            elif op == BatchOperation.DELETE:
                batch.delete(doc_ref)

        await batch.commit()
