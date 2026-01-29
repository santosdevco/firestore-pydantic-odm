"""
Tests to verify no deprecation warnings are raised with Pydantic V2.
"""
import pytest
import warnings

from firestore_pydantic_odm.pydantic_compat import PydanticVersion


pytestmark = pytest.mark.skipif(
    PydanticVersion < 2,
    reason="Deprecation warning tests only apply to Pydantic V2"
)


class TestNoDeprecationWarnings:
    """Tests that verify no deprecation warnings are raised."""

    def test_model_import_no_config_warnings(self):
        """Test that importing models produces no config deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            # Re-import to trigger any config warnings
            from firestore_pydantic_odm import BaseFirestoreModel

            # Define a test model
            class TestModel(BaseFirestoreModel):
                class Settings:
                    name = "test_collection"

                name: str

            # Filter for pydantic-related deprecation warnings
            pydantic_warnings = [
                w for w in caught_warnings
                if "pydantic" in str(w.filename).lower()
                or "pydantic" in str(w.message).lower()
                or "Config" in str(w.message)
                or "allow_population_by_field_name" in str(w.message)
            ]

            assert len(pydantic_warnings) == 0, (
                f"Pydantic deprecation warnings found: "
                f"{[str(w.message) for w in pydantic_warnings]}"
            )

    def test_model_dump_no_dict_warnings(self):
        """Test that model serialization produces no .dict() deprecation warnings."""
        from firestore_pydantic_odm import BaseFirestoreModel
        from firestore_pydantic_odm.pydantic_compat import model_dump_compat

        class TestModel(BaseFirestoreModel):
            class Settings:
                name = "test_collection"

            name: str
            value: int

        instance = TestModel(name="test", value=42)

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            # Call model_dump_compat which should use model_dump() in V2
            result = model_dump_compat(
                instance,
                exclude={"id"},
                exclude_none=True,
                by_alias=True,
            )

            # Filter for .dict() deprecation warnings
            dict_warnings = [
                w for w in caught_warnings
                if ".dict()" in str(w.message)
                or "dict method is deprecated" in str(w.message).lower()
            ]

            assert len(dict_warnings) == 0, (
                f".dict() deprecation warnings found: "
                f"{[str(w.message) for w in dict_warnings]}"
            )

            # Verify the result is correct
            assert result == {"name": "test", "value": 42}

    def test_model_dump_compat_returns_dict(self):
        """Test that model_dump_compat returns a proper dict."""
        from firestore_pydantic_odm import BaseFirestoreModel
        from firestore_pydantic_odm.pydantic_compat import model_dump_compat
        from typing import Optional

        class TestModel(BaseFirestoreModel):
            class Settings:
                name = "test_collection"

            name: str
            optional_field: Optional[str] = None

        instance = TestModel(name="test")

        # Test exclude_none
        result = model_dump_compat(instance, exclude={"id"}, exclude_none=True)
        assert "optional_field" not in result
        assert result == {"name": "test"}

        # Test without exclude_none
        result_with_none = model_dump_compat(instance, exclude={"id"}, exclude_none=False)
        assert "optional_field" in result_with_none
        assert result_with_none["optional_field"] is None

    def test_pydantic_compat_exports(self):
        """Test that pydantic_compat exports all required symbols."""
        from firestore_pydantic_odm.pydantic_compat import (
            BaseModel,
            Field,
            ConfigDict,
            get_model_fields,
            model_dump_compat,
            get_model_config,
            PydanticVersion,
            PYDANTIC_V2_11_PLUS,
        )

        # In Pydantic V2, ConfigDict should not be None
        assert ConfigDict is not None
        assert PydanticVersion >= 2

        # get_model_config should return a dict with proper keys
        config = get_model_config()
        assert isinstance(config, dict)

        # Should have either populate_by_name or validate_by_name
        if PYDANTIC_V2_11_PLUS:
            assert "validate_by_name" in config
            assert "validate_by_alias" in config
        else:
            assert "populate_by_name" in config
