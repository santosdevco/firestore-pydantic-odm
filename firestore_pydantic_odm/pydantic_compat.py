
import pydantic
from packaging.version import parse
from pydantic.version import VERSION

version_parsed = parse(str(VERSION))

if version_parsed.major >= 2:
    print("Estamos en Pydantic V2 o superior.")
    PydanticVersion = 2
else:
    print("Estamos en Pydantic V1.")
    PydanticVersion = 1


BaseModel: type = pydantic.BaseModel
Field: type = pydantic.Field

# Pydantic V1: __fields__; Pydantic V2: model_fields
def get_model_fields(cls: type) -> dict:
    if PydanticVersion == 1:
        return getattr(cls, "__fields__", {})
    else:
        # pydantic.v1.BaseModel en V2 aún define __fields__ para compat,
        # pero lo ideal es usar model_fields en V2. Así cubrimos ambos casos:
        return getattr(cls, "model_fields", {})  # type: ignore[attr-defined]


__all__ = [
    "BaseModel",
    "Field",
    "get_model_fields",
    "PydanticVersion",
]
