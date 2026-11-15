"""Helpers for Peblar."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from peblar import (
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
    PeblarUserConfiguration,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import PeblarEntity


def supports_custom_solar(configuration: PeblarUserConfiguration) -> bool:
    """Return whether the charger knows the custom solar strategy.

    It arrived with firmware 1.10. Rather than check the version, take the
    charger at its word: it reports the settings that go with the strategy,
    and leaves them out when it has never heard of it. Solar charging has
    to be on offer at all for any of it to mean anything.
    """
    return (
        configuration.solar_charging_allowed
        and configuration.solar_charging_custom_power_target is not None
    )


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
