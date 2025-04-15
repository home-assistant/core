"""Helpers for Peblar."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from peblar import PeblarAuthenticationError, PeblarConnectionError, PeblarError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import PeblarEntity


def peblar_exception_handler[_PeblarEntityT: PeblarEntity, **_P](
    func: Callable[Concatenate[_PeblarEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_PeblarEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Peblar calls to handle exceptions.

    A decorator that wraps the passed in function, catches Peblar errors.
    """

    async def handler(
        self: _PeblarEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except PeblarAuthenticationError as error:
            # Reload the config entry to trigger reauth flow
            self.hass.config_entries.async_schedule_reload(
                self.coordinator.config_entry.entry_id
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error

        except PeblarConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

        except PeblarError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
