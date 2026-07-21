"""KNX entity store validation."""

from collections.abc import Callable
from typing import Any, Literal, TypedDict

import probatio as prb

from .entity_store_schema import ENTITY_STORE_DATA_SCHEMA


class _ErrorDescription(TypedDict):
    code: str | None
    message: str
    path: list[str]
    secret: bool
    context: dict[str, Any]
    translation_key: str | None
    placeholders: dict[str, Any]


class EntityStoreValidationError(TypedDict):
    """Negative entity store validation result."""

    success: Literal[False]
    error_base: str
    errors: list[_ErrorDescription]


class EntityStoreValidationSuccess(TypedDict):
    """Positive entity store validation result."""

    success: Literal[True]
    entity_id: str | None


def parse_invalid(exc: prb.Invalid) -> _ErrorDescription:
    """Parse a probatio.Invalid exception."""
    description = exc.as_dict()
    description["path"] = [str(path) for path in description["path"]]
    return description  # type: ignore[return-value]


def validate_config_store_data(
    schema: Callable[[dict], dict], entity_data: dict
) -> dict:
    """Validate data for config store.

    Return validated data or raise EntityStoreValidationException.
    """
    try:
        # return so defaults are applied
        return schema(entity_data)
    except prb.Invalid as exc:
        errors = exc.errors if isinstance(exc, prb.MultipleInvalid) else [exc]
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
