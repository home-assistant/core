"""KNX entity store validation."""

from typing import Any, Literal, TypedDict

import voluptuous as vol

from homeassistant.helpers.typing import VolSchemaType

from .entity_store_schema import ENTITY_STORE_DATA_SCHEMA


class _ErrorDescription(TypedDict):
    path: list[str]
    message: str
    code: str | None
    translation_key: str | None
    placeholders: dict[str, Any]
    context: dict[str, Any]
    secret: bool


class EntityStoreValidationError(TypedDict):
    """Negative entity store validation result."""

    success: Literal[False]
    error_base: str
    errors: list[_ErrorDescription]


class EntityStoreValidationSuccess(TypedDict):
    """Positive entity store validation result."""

    success: Literal[True]
    entity_id: str | None


def parse_invalid(exc: vol.Invalid) -> _ErrorDescription:
    """Parse a vol.Invalid exception."""
    description = exc.as_dict()
    # path items are str or vol.Marker; the frontend matches them against config keys
    description["path"] = [str(path) for path in description["path"]]
    return description  # type: ignore[return-value]


def validate_config_store_data(schema: VolSchemaType, entity_data: dict) -> dict:
    """Validate data for config store.

    Return validated data or raise EntityStoreValidationException.
    """
    try:
        # return so defaults are applied
        return schema(entity_data)  # type: ignore[no-any-return]
    except vol.Invalid as exc:
        errors = exc.errors if isinstance(exc, vol.MultipleInvalid) else [exc]
        raise EntityStoreValidationException(
            validation_error={
                "success": False,
                "error_base": str(exc),
                "errors": [parse_invalid(invalid) for invalid in errors],
            }
        ) from exc


def validate_entity_data(entity_data: dict) -> dict:
    """Validate entity data.

    Return validated data or raise EntityStoreValidationException.
    """
    return validate_config_store_data(ENTITY_STORE_DATA_SCHEMA, entity_data)


class EntityStoreValidationException(Exception):
    """Entity store validation exception."""

    def __init__(self, validation_error: EntityStoreValidationError) -> None:
        """Initialize."""
        super().__init__(validation_error)
        self.validation_error = validation_error
