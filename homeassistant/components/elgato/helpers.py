"""Helpers for Elgato."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from elgato import ElgatoConnectionError, ElgatoError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import ElgatoEntity


def elgato_exception_handler[_ElgatoEntityT: ElgatoEntity, **_P](
    func: Callable[Concatenate[_ElgatoEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_ElgatoEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Elgato calls to handle Elgato exceptions.

    A decorator that wraps the passed in function, catches Elgato errors,
    and raises a translated ``HomeAssistantError``.
    """

    async def handler(
        self: _ElgatoEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except ElgatoConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error
        except ElgatoError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from error

    return handler
