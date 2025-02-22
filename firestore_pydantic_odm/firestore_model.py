import logging
from typing import List, Tuple, Any, Optional, AsyncGenerator, Type, Union
from pydantic import BaseModel, Field
from .enums import BatchOperation,OrderByDirection,FirestoreOperators
from .firestore_client import FirestoreDB
from .firestore_fields import FirestoreQueryMetaclass,FirestoreField
from google.cloud.firestore_v1 import AsyncClient


# Alias de tipo para el primer elemento de la tupla
FieldType = Union[str, FirestoreField]
# Alias de tipo para la tupla
FieldOrderType = Tuple[FieldType, OrderByDirection]


logger = logging.getLogger(__name__)

class BaseFirestoreModel(BaseModel, metaclass=FirestoreQueryMetaclass):
    """
    ODM base para Firestore con operaciones asíncronas.
    """

    # --------------------------------------------------------------------------
    # Campo por defecto (ID del documento)
    # --------------------------------------------------------------------------
    id: Optional[str] = Field(default=None)

    # --------------------------------------------------------------------------
    # Atributo de clase para el FirestoreDB que se usará
    # --------------------------------------------------------------------------
    _db: Optional["FirestoreDB"] = None  # Se inyecta externamente

    # --------------------------------------------------------------------------
    # Definición de la colección
    # --------------------------------------------------------------------------
    class Settings:
        name: str = "BaseCollection"  # Sobrescribir en subclases

    # --------------------------------------------------------------------------
    # Config de Pydantic
    # --------------------------------------------------------------------------
    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True

    # --------------------------------------------------------------------------
    # Métodos de inicialización del DB (inyección)
    # --------------------------------------------------------------------------
    @classmethod
    def initialize_db(cls, db: "FirestoreDB"):
        """
        Inyecta el objeto FirestoreDB que se usará para todas las operaciones.
        """
        cls._db = db

    @property
    def collection_name(self) -> str:
        """
        Retorna el nombre de la colección de este modelo.
        """
        if hasattr(self, "Settings") and hasattr(self.Settings, "name"):
            return self.Settings.name
        return self.__class__.__name__

    @classmethod
    def get_collection_name(cls) -> str:
        """
        Versión de clase para obtener el nombre de la colección.
        """
        if hasattr(cls, "Settings") and hasattr(cls.Settings, "name"):
            return cls.Settings.name
        return cls.__name__

    # --------------------------------------------------------------------------
    # CRUD Asíncrono (create/update/delete)
    # --------------------------------------------------------------------------
    async def save(self,exclude_none=True,by_alias=True,exclude_unset=True) -> "BaseFirestoreModel":
        """
        Crea o sobrescribe el documento en Firestore de manera asíncrona.
        """
        if not self._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = self._db.client

        data_to_save = self.dict(exclude={"id"}, exclude_unset=exclude_unset, exclude_none=exclude_none,by_alias=by_alias)
        collection_ref = db_client.collection(self.collection_name)

        if not self.id:
            doc_ref = collection_ref.document()
            self.id = doc_ref.id
        else:
            doc_ref = collection_ref.document(self.id)

        await doc_ref.set(data_to_save)
        return self

    async def update(self, include: Optional[set] = None,exclude_none=True,by_alias=True,exclude_unset=True) -> "BaseFirestoreModel":
        """
        Actualiza campos en un documento existente en Firestore.
        """
        if not self._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = self._db.client

        if not self.id:
            raise ValueError("No se puede actualizar un documento sin un ID.")

        doc_ref = db_client.collection(self.collection_name).document(self.id)

        if include:
            updates = self.dict(exclude={"id"}, include=include, exclude_unset=exclude_unset, exclude_none=exclude_none,by_alias=by_alias)
        else:
            updates = self.dict(exclude={"id"}, exclude_unset=exclude_unset, exclude_none=exclude_none,by_alias=by_alias)

        logger.debug(f"Update: {self.collection_name} - id={self.id}, updates={updates}")
        if updates:
            await doc_ref.update(updates)
        return self

    async def delete(self) -> None:
        """
        Elimina el documento en Firestore.
        """
        if not self._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = self._db.client

        if not self.id:
            raise ValueError("No se puede eliminar un documento sin un ID.")

        doc_ref = db_client.collection(self.collection_name).document(self.id)
        await doc_ref.delete()

    # --------------------------------------------------------------------------
    # Obtener un doc por ID
    # --------------------------------------------------------------------------
    @classmethod
    async def get(cls, doc_id: str) -> Optional["BaseFirestoreModel"]:
        """
        Obtiene un documento por su ID.
        """
        if not cls._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = cls._db.client

        doc_ref = db_client.collection(cls.get_collection_name()).document(doc_id)
        doc_snap = await doc_ref.get()

        if doc_snap.exists:
            data = doc_snap.to_dict()
            data["id"] = doc_snap.id
            return cls(**data)
        return None

    # --------------------------------------------------------------------------
    # Contar documentos
    # --------------------------------------------------------------------------
    @classmethod
    async def count(cls, filters: List[Tuple[str, str, Any]]) -> int:
        """
        Retorna el número de documentos que cumplen los filtros.
        Si tu SDK no soporta .count(), puedes hacer un approach manual.
        """
        if not cls._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = cls._db.client

        query = cls._build_query(db_client, filters=filters)
        try:
            # Firestore 2.11+ en adelante
            count_snapshot = await query.count().get()
            # Devuelve una lista de agregaciones; la primera es count
            return count_snapshot[0][0].value
        except AttributeError:
            logger.warning("Firestore: Performing count downloading all items with empty select")
            # Si tu librería no soporta count(), fallback manual
            docs = await query.select([]).get()
            return len(docs)

    # --------------------------------------------------------------------------
    # Find (generador asíncrono)
    # --------------------------------------------------------------------------
    
    @classmethod
    async def find(
        cls,
        filters: List[Tuple[FieldType, FirestoreOperators, Any]] = None,
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[Union[List[Union[FieldType, FieldOrderType]],Union[FieldType, FieldOrderType]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> AsyncGenerator[Union["BaseFirestoreModel",Type[BaseModel]], None]:
        """
        Busca documentos que cumplan los filtros y los retorna como generador asíncrono.

        :param filters: Lista de tuplas (campo, operador, valor).
        :param projection: Clase Pydantic para proyectar campos (ej. PartialModel).
                           Si es None, se traen todos los campos.
        :param order_by: Campo para ordenar (puede ser FirestoreField o string).
        :param limit: Máximo de documentos a retornar.
        :param offset: Desplazamiento (para paginación).
        :return: AsyncGenerator que produce instancias de `cls`.
        """
        if not cls._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = cls._db.client

        filters = filters or []
        query = cls._build_query(db_client, filters=filters, projection=projection)

        # Ordenación
        if order_by :
            if type(order_by) != list:
                order_by= [order_by]
            for order_by_field in order_by:
                order_by_kwargs = {}

                if type(order_by_field) == tuple:
                    field,direction=order_by_field
                    order_by_kwargs={"direction":str(direction)}
                else:
                    field = order_by_field
                # Si es un FirestoreField, lo convertimos a string.
                if isinstance(field, FirestoreField):
                    field = str(field)
                query = query.order_by(field,**order_by_kwargs)

        # Paginación
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        # Firestore asíncrono permite stream()
        docs = query.stream()
        constructor  = cls if projection is None else projection
        async for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            yield constructor(**data)

    # --------------------------------------------------------------------------
    # Find one (retorna el primer documento que cumpla filtros)
    # --------------------------------------------------------------------------
    @classmethod
    async def find_one(
        cls,
        filters: List[Tuple[str, str, Any]],
        projection: Optional[Type[BaseModel]] = None,
        order_by: Optional[Union[FieldType, FieldOrderType]] = None,
    ) -> Optional["BaseFirestoreModel"]:
        """
        Retorna un único documento que cumpla los filtros (o None si no hay).
        Soporta proyección y ordenación.
        """
        async for obj in cls.find(
            filters=filters,
            projection=projection,
            order_by=order_by,
            limit=1
        ):
            return obj
        return None

    # --------------------------------------------------------------------------
    # Build query interno
    # --------------------------------------------------------------------------
    @classmethod
    def _build_query(cls, db_client: AsyncClient , filters: List[Tuple[str, str, Any]], projection: Optional[Type[BaseModel]] = None):
        """
        Construye la query de Firestore aplicando filtros y proyección.
        """
        collection_ref = db_client.collection(cls.get_collection_name())
        query = collection_ref

        # Aplicar los filtros
        for (field_name, op, value) in filters:
            # query = query.where(field_name, op, value)
            # query = query.filter((field_name, op, value))
            # query = query.where(field_name=field_name, op_string=op, value=value)
            query = query.where(field_path=field_name, op_string=op, value=value)
            

        # Proyección
        # Si se proporciona un modelo Pydantic para projection, tomamos sus campos
        if projection is not None:
            if hasattr(projection, "model_fields"):
                select_fields = list(projection.model_fields.keys())  # Pydantic v2
            else:
                select_fields = list(projection.schema()["properties"].keys())  # Pydantic v1
            logger.debug(f"Build Query: select fields: {select_fields}")
            query = query.select(select_fields)

        return query

    # --------------------------------------------------------------------------
    # Batch operations
    # --------------------------------------------------------------------------
    @classmethod
    async def batch_write(cls, operations: List[Tuple["BatchOperation", "BaseFirestoreModel"]]):
        """
        Ejecuta operaciones en batch (create, update, delete) de forma atómica.
        """
        if not cls._db:
            raise RuntimeError("Debe inicializar el DB antes de usar el modelo.")
        db_client = cls._db.client

        batch = db_client.batch()

        for op, model_instance in operations:
            collection_ref = db_client.collection(model_instance.collection_name)

            # Determinar el doc_ref
            if not model_instance.id and op != BatchOperation.CREATE:
                raise ValueError(f"No se puede {op} sin ID asignado en {model_instance}.")

            doc_ref = collection_ref.document(model_instance.id) if model_instance.id else collection_ref.document()

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
