"""Helpers for AdGuard Home."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def adguard_exception_handler[**_P](
    func: Callable[_P, Coroutine[Any, Any, None]],
) -> Callable[_P, Coroutine[Any, Any, None]]:
    """Decorate AdGuard Home calls to raise translated Home Assistant errors."""

    @wraps(func)
    async def handler(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(*args, **kwargs)

        except AdGuardHomeConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from error

        except AdGuardHomeAuthenticationError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from error

        except AdGuardHomeError as error:
            # AdGuard Home explains what went wrong, like an unknown list.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
