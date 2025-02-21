from enum import Enum

class BatchOperation(str,Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
