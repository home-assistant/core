"""KNX expose store validation."""

from typing import Literal, TypedDict

import voluptuous as vol

from ..expose import ExposeSchema


class _ErrorDescription(TypedDict):
    path: list[str] | None
    error_message: str
    error_class: str


class ExposeStoreValidationError(TypedDict):
    """Negative expose store validation result."""

    success: Literal[False]
    error_base: str
    errors: list[_ErrorDescription]


class ExposeStoreValidationSuccess(TypedDict):
    """Positive expose store validation result."""

    success: Literal[True]
    expose_address: str


def parse_invalid(exc: vol.Invalid) -> _ErrorDescription:
    """Parse a vol.Invalid exception."""
    return _ErrorDescription(
        path=[str(path) for path in exc.path],  # exc.path: str | vol.Required
        error_message=exc.msg,
        error_class=type(exc).__name__,
    )


def validate_expose_data(expose_data: dict) -> dict:
    """Validate expose data.

    Return validated data or raise ExposeStoreValidationException.
    """
    try:
        # return so defaults are applied
        return ExposeSchema.ENTITY_SCHEMA(expose_data)  # type: ignore[no-any-return]
    except vol.MultipleInvalid as exc:
        raise ExposeStoreValidationException(
            validation_error={
                "success": False,
                "error_base": str(exc),
                "errors": [parse_invalid(invalid) for invalid in exc.errors],
            }
        ) from exc
    except vol.Invalid as exc:
        raise ExposeStoreValidationException(
            validation_error={
                "success": False,
                "error_base": str(exc),
                "errors": [parse_invalid(exc)],
            }
        ) from exc


class ExposeStoreValidationException(Exception):
    """Expose store validation exception."""

    def __init__(self, validation_error: ExposeStoreValidationError) -> None:
        """Initialize."""
        super().__init__(validation_error)
        self.validation_error = validation_error
