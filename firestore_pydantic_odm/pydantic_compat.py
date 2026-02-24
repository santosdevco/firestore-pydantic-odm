
import pydantic
from packaging.version import parse
from pydantic.version import VERSION

version_parsed = parse(str(VERSION))

if version_parsed.major >= 2:
    PydanticVersion = 2
    # Check for v2.11+ which renamed config keys
    PYDANTIC_V2_11_PLUS = version_parsed >= parse("2.11.0")
else:
    PydanticVersion = 1
    PYDANTIC_V2_11_PLUS = False


BaseModel: type = pydantic.BaseModel
Field: type = pydantic.Field
PrivateAttr: type = pydantic.PrivateAttr

# Import ConfigDict for Pydantic V2, None for V1
if PydanticVersion >= 2:
    from pydantic import ConfigDict
else:
    ConfigDict = None  # type: ignore[misc, assignment]


# Pydantic V1: __fields__; Pydantic V2: model_fields
def get_model_fields(cls: type) -> dict:
    if PydanticVersion == 1:
        return getattr(cls, "__fields__", {})
    else:
        # pydantic.v1.BaseModel en V2 aún define __fields__ para compat,
        # pero lo ideal es usar model_fields en V2. Así cubrimos ambos casos:
        return getattr(cls, "model_fields", {})  # type: ignore[attr-defined]


def model_dump_compat(instance: BaseModel, **kwargs) -> dict:
    """
    Compatibility wrapper for model serialization.
    Uses .model_dump() for Pydantic V2, .dict() for V1.
    """
    if PydanticVersion >= 2:
        return instance.model_dump(**kwargs)
    else:
        return instance.dict(**kwargs)


def get_model_config() -> dict:
    """
    Returns the appropriate model config for the current Pydantic version.
    For V2.11+: uses validate_by_name and validate_by_alias
    For V2 < 2.11: uses populate_by_name
    For V1: returns empty dict (Config class should be used instead)
    """
    if PydanticVersion >= 2:
        if PYDANTIC_V2_11_PLUS:
            return {
                "validate_by_name": True,
                "validate_by_alias": True,
            }
        else:
            return {
                "populate_by_name": True,
            }
    return {}


__all__ = [
    "BaseModel",
    "Field",
    "PrivateAttr",
    "ConfigDict",
    "get_model_fields",
    "model_dump_compat",
    "get_model_config",
    "PydanticVersion",
    "PYDANTIC_V2_11_PLUS",
]
