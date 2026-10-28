"""Utilities for the Seafile integration."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from aioseafile import SeafileError, SeafilePermissionError, SeafileTimeoutError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def handle_seafile_errors[_R, **_P](
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Raise translated errors for failed Seafile API calls."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except SeafilePermissionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="permission_denied"
            ) from err
        except SeafileTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="timeout_connect"
            ) from err
        except SeafileError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err

    return wrapper
