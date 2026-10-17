"""Translate Zentraly action errors at the Home Assistant boundary."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from zentraly import (
    ZentralyApiError,
    ZentralyCommandRejectedError,
    ZentralyConnectionBusyError,
    ZentralyConnectionError,
    ZentralyInvalidResponseError,
    ZentralyValidationError,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN


def translate_action_errors[**P, R](
    action: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Convert protocol errors without exposing technical details to the UI."""

    @wraps(action)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await action(*args, **kwargs)
        except ZentralyValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_action"
            ) from err
        except ZentralyApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=_error_key(err)
            ) from err

    return wrapped


def _error_key(error: ZentralyApiError) -> str:
    """Map library failures to integration translation keys."""
    for error_type, key in (
        (ZentralyConnectionBusyError, "connection_busy"),
        (ZentralyConnectionError, "cannot_connect"),
        (ZentralyInvalidResponseError, "invalid_response"),
        (ZentralyCommandRejectedError, "command_rejected"),
    ):
        if isinstance(error, error_type):
            return key
    return "action_failed"
