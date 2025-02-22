from enum import Enum


class BatchOperation(str,Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class FirestoreOperators(str,Enum):
    LT = "<"
    LTE = "<="
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    IN = "in"
    NOT_IN = "not-in"
    ARRAY_CONTAINS = "array_contains"
    ARRAY_CONTAINS_ANY = "array_contains_any"

class OrderByDirection(str,Enum):
    DESCENDING="DESCENDING"
    ASCENDING="ASCENDING"
    def __str__(self):
        return self.value
