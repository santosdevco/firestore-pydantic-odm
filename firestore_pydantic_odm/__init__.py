# mi_firestore_odm/__init__.py
from typing import List
from .firestore_model import BaseFirestoreModel
from .firestore_fields import FirestoreField
from .firestore_client import FirestoreDB
from .enums import BatchOperation, FirestoreOperators, OrderByDirection


def init_firestore_odm(database,document_models:List[BaseFirestoreModel]):
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
    "init_firestore_odm"
]
