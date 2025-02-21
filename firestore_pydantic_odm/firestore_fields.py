from typing import Any, List

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
        return (self.field_name, "==", other)

    def __ne__(self, other):
        return (self.field_name, "!=", other)

    def __lt__(self, other):
        return (self.field_name, "<", other)

    def __le__(self, other):
        return (self.field_name, "<=", other)

    def __gt__(self, other):
        return (self.field_name, ">", other)

    def __ge__(self, other):
        return (self.field_name, ">=", other)

    # Operadores específicos de Firestore
    def in_(self, values: List[Any]) -> tuple:
        return (self.field_name, "in", values)

    def array_contains(self, value: Any) -> tuple:
        return (self.field_name, "array_contains", value)

    def array_contains_any(self, values: List[Any]) -> tuple:
        return (self.field_name, "array_contains_any", values)


from pydantic.main import ModelMetaclass

class FirestoreQueryMetaclass(ModelMetaclass):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # Insertar FirestoreField en cada campo pydantic
        if hasattr(cls, "__fields__"):
            for field_name, model_field in cls.__fields__.items():
                alias = model_field.alias or field_name
                setattr(cls, field_name, FirestoreField(alias))
        return cls
