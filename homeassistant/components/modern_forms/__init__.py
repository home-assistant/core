"""The Modern Forms integration."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from aiomodernforms import ModernFormsConnectionError, ModernFormsError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Modern Forms integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ModernFormsConfigEntry) -> bool:
    """Set up a Modern Forms device from a config entry."""

    # Create Modern Forms instance for this entry
    coordinator = ModernFormsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModernFormsConfigEntry
) -> bool:
    """Unload Modern Forms config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def modernforms_exception_handler[
    _ModernFormsDeviceEntityT: ModernFormsDeviceEntity,
    **_P,
](
    func: Callable[Concatenate[_ModernFormsDeviceEntityT, _P], Any],
) -> Callable[Concatenate[_ModernFormsDeviceEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Modern Forms calls to handle Modern Forms exceptions.

    A decorator that wraps the passed in function, catches Modern Forms errors,
    and raises translated HomeAssistantError exceptions.
    """

    async def handler(
        self: _ModernFormsDeviceEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except ModernFormsConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        except ModernFormsError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error

    return handler
