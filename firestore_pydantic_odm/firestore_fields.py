from typing import Any, List


from .enums import FirestoreOperators


class FirestoreField:
    """
    Lightweight *descriptor* that allows class-level attribute access
    to build Firestore filters.

    Examples
    --------
    >>> User.age >= 18
    ('age', FirestoreOperators.GTE, 18)

    When accessed on an **instance** the real value is returned,
    while a class-level access yields the descriptor so that rich
    comparison operators can be chained to create query tuples.  
    See the Python descriptor HOW-TO for details on ``__get__`` mechanics.:contentReference[oaicite:0]{index=0}
    """

    def __init__(self, field_name: str):
        self.field_name = field_name

    # ------------------------------------------------------------------ #
    # Descriptor protocol                                                #
    # ------------------------------------------------------------------ #

    def __get__(self, instance, owner):
        """
        Instance access → return the actual value.
        Class access   → return *self* for later comparisons.
        """
        # Class-level access
        if instance is None:
            return self
        # Instance-level access
        return getattr(instance, self.field_name, None)

    # ------------------------------------------------------------------ #
    # Convenience dunder methods                                         #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:          # noqa: DunderStr
        return self.field_name

    __repr__ = __str__

    def __hash__(self) -> int:         # noqa: DunderHash
        return hash(self.field_name)

    # ------------------------------------------------------------------ #
    # Comparison operators build (field, operator, value) tuples         #
    # ------------------------------------------------------------------ #

    def __eq__(self, other):           # type: ignore[override]
        return (self.field_name, FirestoreOperators.EQ, other)

    def __ne__(self, other):           # type: ignore[override]
        return (self.field_name, FirestoreOperators.NE, other)

    def __lt__(self, other):
        return (self.field_name, FirestoreOperators.LT, other)

    def __le__(self, other):
        return (self.field_name, FirestoreOperators.LTE, other)

    def __gt__(self, other):
        return (self.field_name, FirestoreOperators.GT, other)

    def __ge__(self, other):
        return (self.field_name, FirestoreOperators.GTE, other)

    # ------------------------------------------------------------------ #
    # Firestore-specific helpers                                         #
    # ------------------------------------------------------------------ #

    def in_(self, values: List[Any]) -> tuple:
        """Return an ``IN`` filter tuple.:contentReference[oaicite:1]{index=1}"""
        return (self.field_name, FirestoreOperators.IN, values)

    def not_in_(self, values: List[Any]) -> tuple:
        """Return a ``NOT_IN`` filter tuple.:contentReference[oaicite:2]{index=2}"""
        return (self.field_name, FirestoreOperators.NOT_IN, values)

    def array_contains(self, value: Any) -> tuple:
        """Return an ``ARRAY_CONTAINS`` filter tuple.:contentReference[oaicite:3]{index=3}"""
        return (self.field_name, FirestoreOperators.ARRAY_CONTAINS, value)

    def array_contains_any(self, values: List[Any]) -> tuple:
        """Return an ``ARRAY_CONTAINS_ANY`` filter tuple.:contentReference[oaicite:4]{index=4}"""
        return (self.field_name, FirestoreOperators.ARRAY_CONTAINS_ANY, values)



