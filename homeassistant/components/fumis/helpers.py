"""Helpers for Fumis."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from fumis import (
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisStoveOfflineError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import FumisEntity


def fumis_exception_handler[_FumisEntityT: FumisEntity, **_P](
    func: Callable[Concatenate[_FumisEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_FumisEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Fumis calls to handle exceptions.

    A decorator that wraps the passed in function, catches Fumis errors.
    """

    async def handler(self: _FumisEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except FumisAuthenticationError as error:
            self.hass.config_entries.async_schedule_reload(
                self.coordinator.config_entry.entry_id
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error

        except FumisStoveOfflineError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stove_offline",
            ) from error

        except FumisConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

        except FumisError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
