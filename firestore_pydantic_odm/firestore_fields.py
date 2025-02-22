from typing import Any, List
from .enums import FirestoreOperators
# from google.cloud import firestore
from google.cloud.firestore_v1.field_path import FieldPath



class FirestoreField:
    """
    Descriptor que, al hacer MyModel.field a nivel de clase,
    permite construir expresiones de filtro (e.g. MyModel.field == valor).
    """
    def __init__(self, field_name: str):
        self.field_name = field_name

    def __get__(self, instance, owner):
        # Acceso en modo de clase -> retorna self para filtros
        # Acceso en instancia -> obtiene el valor real
        if instance is None:
            return self
        return getattr(instance, self.field_name, None)

    def __str__(self):
        return self.field_name

    def __repr__(self):
        return self.field_name

    def __hash__(self):
        return hash(self.field_name)

    def __eq__(self, other):
        return (self.field_name, FirestoreOperators.EQ, other)

    def __ne__(self, other):
        return (self.field_name, FirestoreOperators.NE, other)

    def __lt__(self, other):
        return (self.field_name, FirestoreOperators.LT, other)

    def __le__(self, other):
        return (self.field_name, FirestoreOperators.LTE, other)

    def __gt__(self, other):
        return (self.field_name, FirestoreOperators.GT, other)

    def __ge__(self, other):
        return (self.field_name, FirestoreOperators.GTE, other)

    # Operadores específicos de Firestore
    def in_(self, values: List[Any]) -> tuple:
        return (self.field_name, FirestoreOperators.IN, values)
    # Operadores específicos de Firestore
    def not_in_(self, values: List[Any]) -> tuple:
        return (self.field_name, FirestoreOperators.NOT_IN, values)

    def array_contains(self, value: Any) -> tuple:
        return (self.field_name, FirestoreOperators.ARRAY_CONTAINS, value)

    def array_contains_any(self, values: List[Any]) -> tuple:
        return (self.field_name, FirestoreOperators.ARRAY_CONTAINS_ANY, values)


from pydantic.main import ModelMetaclass
class FirestoreQueryMetaclass(ModelMetaclass):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # Verificar si la clase tiene campos de Pydantic
        fields = getattr(cls, "__fields__", {})
        for field_name, model_field in fields.items():
            alias = FieldPath.document_id() if field_name == "id" else model_field.alias or field_name
            setattr(cls, field_name, FirestoreField(alias))

        return cls
