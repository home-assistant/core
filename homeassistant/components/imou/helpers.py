"""Helpers for Imou."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import ImouEntity


def async_wrap_imou_command[_T: ImouEntity, **_P, _R](
    error_key: str,
) -> Callable[
    [Callable[Concatenate[_T, _P], Awaitable[_R]]],
    Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]],
]:
    """Wrap an Imou command and start reauthentication when credentials are rejected."""

    def decorator(
        func: Callable[Concatenate[_T, _P], Awaitable[_R]],
    ) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:
        @wraps(func)
        async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
            try:
                return await func(self, *args, **kwargs)
            except InvalidAppIdOrSecretException as err:
                self.coordinator.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from err
            except ImouException as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=error_key,
                ) from err

        return wrapper

    return decorator
