# mi_firestore_odm/__init__.py
from typing import List
from .firestore_model import BaseFirestoreModel
from .firestore_fields import FirestoreField
from .firestore_client import FirestoreDB
from .enums import BatchOperation, FirestoreOperators, OrderByDirection
from .subcollection_accessor import SubCollectionAccessor


def init_firestore_odm(database,document_models:List[BaseFirestoreModel]):
    # Store registry for cascade delete discovery
    BaseFirestoreModel._registered_models = list(document_models)

    for model in document_models:
        model.initialize_db(database)
        model.initialize_fields()

__all__ = [
    "BaseFirestoreModel",
    "FirestoreField",
    "FirestoreDB",
    "BatchOperation",
    "FirestoreOperators",
    "OrderByDirection",
    "SubCollectionAccessor",
    "init_firestore_odm"
]
