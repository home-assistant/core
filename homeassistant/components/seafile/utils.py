"""Utilities for the Seafile integration."""

from collections.abc import Callable, Coroutine
from functools import wraps
from types import TracebackType
from typing import Any

from aioseafile import SeafileError, SeafilePermissionError, SeafileTimeoutError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER


class SeafileErrorHandler:
    """Raise translated errors for failed Seafile API calls.

    Works as a decorator for coroutine functions and as a context manager.
    """

    def __init__(
        self,
        error: type[HomeAssistantError],
        translation_domain: str,
        *,
        failed: str,
        timed_out: str,
        not_allowed: str | None = None,
    ) -> None:
        """Initialize the handler with the error to raise and its translations."""
        self._error = error
        self._translation_domain = translation_domain
        self._failed = failed
        self._timed_out = timed_out
        self._not_allowed = not_allowed

    def __enter__(self) -> None:
        """Enter the context."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Raise a translated error for a Seafile error."""
        if not isinstance(exc, SeafileError):
            return
        if self._not_allowed is not None and isinstance(exc, SeafilePermissionError):
            translation_key = self._not_allowed
        elif isinstance(exc, SeafileTimeoutError):
            translation_key = self._timed_out
        else:
            LOGGER.debug("Seafile API call failed: %s", exc)
            translation_key = self._failed
        raise self._error(
            translation_domain=self._translation_domain,
            translation_key=translation_key,
        ) from exc

    def __call__[_R, **_P](
        self, func: Callable[_P, Coroutine[Any, Any, _R]]
    ) -> Callable[_P, Coroutine[Any, Any, _R]]:
        """Decorate a coroutine function."""

        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            with self:
                return await func(*args, **kwargs)

        return wrapper


handle_seafile_errors = SeafileErrorHandler(
    HomeAssistantError,
    DOMAIN,
    failed="api_error",
    timed_out="timeout_connect",
    not_allowed="permission_denied",
)
