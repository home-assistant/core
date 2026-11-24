"""Helpers for the Samsung ExLink integration."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from samsung_exlink import CommandRejected, SamsungTVError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def catch_command_errors[**_P](
    func: Callable[_P, Coroutine[Any, Any, None]],
) -> Callable[_P, Coroutine[Any, Any, None]]:
    """Translate Samsung library errors raised by an action into HomeAssistantError."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except CommandRejected as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err
        except (SamsungTVError, ConnectionError, OSError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    return wrapper
