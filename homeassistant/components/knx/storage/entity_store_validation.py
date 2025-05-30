"""KNX Entity Store Validation."""

from typing import Literal, TypedDict

import voluptuous as vol

from .entity_store_schema import ENTITY_STORE_DATA_SCHEMA


class _ErrorDescription(TypedDict):
    path: list[str] | None
    error_message: str
    error_class: str


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
    return _ErrorDescription(
        path=[str(path) for path in exc.path],  # exc.path: str | vol.Required
        error_message=exc.msg,
        error_class=type(exc).__name__,
    )


def validate_entity_data(entity_data: dict) -> dict:
    """Validate entity data.

    Return validated data or raise EntityStoreValidationException.
    """
    try:
        # return so defaults are applied
        return ENTITY_STORE_DATA_SCHEMA(entity_data)  # type: ignore[no-any-return]
    except vol.MultipleInvalid as exc:
        raise EntityStoreValidationException(
            validation_error={
                "success": False,
                "error_base": str(exc),
                "errors": [parse_invalid(invalid) for invalid in exc.errors],
            }
        ) from exc
    except vol.Invalid as exc:
        raise EntityStoreValidationException(
            validation_error={
                "success": False,
                "error_base": str(exc),
                "errors": [parse_invalid(exc)],
            }
        ) from exc


class EntityStoreValidationException(Exception):
    """Entity store validation exception."""

    def __init__(self, validation_error: EntityStoreValidationError) -> None:
        """Initialize."""
        super().__init__(validation_error)
        self.validation_error = validation_error
