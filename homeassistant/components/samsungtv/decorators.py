"""Decorators for samsungtv media player commands."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, TypeVar, cast

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER

_CoroT = TypeVar("_CoroT", bound=Callable[..., Coroutine[Any, Any, Any]])


def cmd(
    func: _CoroT,
) -> _CoroT:
    """Decorate a media player command with centralized error handling.

    Catches unexpected exceptions raised during command execution, logs them,
    and raises a HomeAssistantError with a translation key.
    HomeAssistantError and CancelledError are re-raised unchanged.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HomeAssistantError, asyncio.CancelledError:
            raise
        except Exception as err:
            entity_id = args[0].entity_id if args else ""
            LOGGER.exception(
                "Error executing %s on %s",
                func.__name__,
                entity_id,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={
                    "entity": entity_id,
                    "command": func.__name__,
                    "error": repr(err),
                },
            ) from err

    return cast(_CoroT, wrapper)
