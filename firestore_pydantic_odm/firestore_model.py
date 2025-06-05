import logging
from typing import List, Tuple, Any, Optional, AsyncGenerator, Type, Union
from .pydantic_compat import BaseModel, Field, get_model_fields
from .enums import BatchOperation, OrderByDirection, FirestoreOperators
from .firestore_client import FirestoreDB
from .firestore_fields import  FirestoreField
from google.cloud.firestore_v1 import AsyncClient
from google.cloud.firestore_v1.field_path import FieldPath


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
    _db: Optional["FirestoreDB"] = None  # Injected externally

    # --------------------------------------------------------------------------
    # Collection definition
    # --------------------------------------------------------------------------
    class Settings:
        name: str = "BaseCollection"  # Override in subclasses

    # --------------------------------------------------------------------------
    # Pydantic configuration
    # --------------------------------------------------------------------------
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
    # CRUD operations: create/update/delete
    # --------------------------------------------------------------------------
    async def save(self, exclude_none=True, by_alias=True, exclude_unset=True) -> "BaseFirestoreModel":
        """
        Create the document in Firestore asynchronously.
        """
        if not self._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = self._db.client

        data_to_save = self.dict(
            exclude={"id"},
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            by_alias=by_alias,
        )
        collection_ref = db_client.collection(self.collection_name)

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

        doc_ref = db_client.collection(self.collection_name).document(self.id)

        if include:
            updates = self.dict(
                exclude={"id"},
                include=include,
                exclude_unset=exclude_unset,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
        else:
            updates = self.dict(
                exclude={"id"},
                exclude_unset=exclude_unset,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )

        logger.debug(f"Update: {self.collection_name} - id={self.id}, updates={updates}")
        if updates:
            await doc_ref.update(updates)
        return self

    async def delete(self) -> None:
        """
        Delete the document from Firestore.
        """
        if not self._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = self._db.client

        if not self.id:
            raise ValueError("Cannot delete a document without an ID.")

        doc_ref = db_client.collection(self.collection_name).document(self.id)
        await doc_ref.delete()

    # --------------------------------------------------------------------------
    # Get a document by ID
    # --------------------------------------------------------------------------
    @classmethod
    async def get(cls, doc_id: str) -> Optional["BaseFirestoreModel"]:
        """
        Retrieve a document by its ID.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        doc_ref = db_client.collection(cls.get_collection_name()).document(doc_id)
        doc_snap = await doc_ref.get()

        if doc_snap.exists:
            data = doc_snap.to_dict()
            data["id"] = doc_snap.id
            return cls(**data)
        return None

    # --------------------------------------------------------------------------
    # Check if a document exists by ID
    # --------------------------------------------------------------------------
    @classmethod
    async def exists(cls, doc_id: str) -> bool:
        """
        Return True if a document with the given ID exists in Firestore.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        doc_ref = db_client.collection(cls.get_collection_name()).document(doc_id)
        doc_snap = await doc_ref.get()
        return doc_snap.exists

    # --------------------------------------------------------------------------
    # Count documents
    # --------------------------------------------------------------------------
    @classmethod
    async def count(cls, filters: List[Tuple[str, str, Any]]) -> int:
        """
        Return the number of documents matching the given filters.
        If the SDK does not support .count(), a manual approach is used.
        """
        if not cls._db:
            raise RuntimeError("Database must be initialized before using the model.")
        db_client = cls._db.client

        query = cls._build_query(db_client, filters=filters)
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
        query = cls._build_query(db_client, filters=filters, projection=projection)

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
            yield constructor(**data)

    # --------------------------------------------------------------------------
    # Find one (first matching document)
    # --------------------------------------------------------------------------
    @classmethod
    async def find_one(
        cls,
        filters: List[Tuple[str, str, Any]],
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[Union[FieldType, FieldOrderType]] = None,
    ) -> Optional["BaseFirestoreModel"]:
        """
        Return the first document matching filters, or None if no match.
        """
        async for obj in cls.find(
            filters=filters, projection=projection, order_by=order_by, limit=1
        ):
            return obj
        return None

    # --------------------------------------------------------------------------
    # Internal query builder
    # --------------------------------------------------------------------------
    @classmethod
    def _build_query(
        cls, db_client: AsyncClient, filters: List[Tuple[str, str, Any]], projection: Optional[Type[BaseModel]] = None
    ):
        """
        Build a Firestore query applying filters and optional projection.
        """
        collection_ref = db_client.collection(cls.get_collection_name())
        query = collection_ref

        # Apply filters
        for (field_name, op, value) in filters:
            query = query.where(field_path=field_name, op_string=op, value=value)

        # Projection
        if projection:
            if hasattr(projection, "model_fields"):
                select_fields = list(projection.model_fields.keys())
            else:
                select_fields = list(projection.schema()["properties"].keys())
            logger.debug(f"Build Query: select fields: {select_fields}")
            query = query.select(select_fields)

        return query

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
            collection_ref = db_client.collection(model_instance.collection_name)

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
                data_to_save = model_instance.dict(exclude={"id"}, exclude_none=True)
                batch.set(doc_ref, data_to_save)

            elif op == BatchOperation.UPDATE:
                data_to_update = model_instance.dict(exclude={"id"}, exclude_none=True)
                batch.update(doc_ref, data_to_update)

            elif op == BatchOperation.DELETE:
                batch.delete(doc_ref)

        await batch.commit()
