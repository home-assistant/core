"""Support for Elgato Lights."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    ElgatoConfigEntry,
    ElgatoDataUpdateCoordinator,
    ElgatoFirmwareCoordinator,
)
from .services import async_setup_services

ELGATO_KEY: HassKey[ElgatoFirmwareCoordinator] = HassKey(DOMAIN)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component.

    Elgato publishes one firmware catalog covering every model, so a single
    coordinator serves every device rather than each config entry fetching
    the same thing.
    """
    async_setup_services(hass)

    coordinator = ElgatoFirmwareCoordinator(hass)
    hass.data[ELGATO_KEY] = coordinator

    # Elgato's servers are not on the local network and a request to them can
    # sit there for its full timeout, so nothing waits on this. The update
    # entities fill themselves in once the answer arrives.
    hass.async_create_background_task(
        coordinator.async_refresh(), f"{DOMAIN}_firmware_refresh"
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Set up Elgato Light from a config entry."""
    coordinator = ElgatoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
