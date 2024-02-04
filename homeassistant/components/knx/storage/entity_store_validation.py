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


def validate_entity_data(entity_data: dict) -> EntityStoreValidationError | None:
    """Validate entity data. Return `None` if valid."""
    try:
        ENTITY_STORE_DATA_SCHEMA(entity_data)
    except vol.MultipleInvalid as exc:
        return {
            "success": False,
            "error_base": str(exc),
            "errors": [parse_invalid(invalid) for invalid in exc.errors],
        }
    except vol.Invalid as exc:
        return {
            "success": False,
            "error_base": str(exc),
            "errors": [parse_invalid(exc)],
        }
    return None
