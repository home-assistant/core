"""Support for Elgato Lights."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import (
    ElgatoConfigEntry,
    ElgatoCoordinators,
    ElgatoDataUpdateCoordinator,
    ElgatoFirmwareCoordinator,
)
from .services import async_setup_services

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
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Set up Elgato Light from a config entry."""
    coordinator = ElgatoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    firmware = ElgatoFirmwareCoordinator(
        hass, entry, coordinator.data.info.hardware_board_type
    )

    entry.runtime_data = ElgatoCoordinators(device=coordinator, firmware=firmware)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Elgato's servers are not on the local network, and a request to them
    # can sit there for its full timeout. A light on your own network has no
    # business waiting on that, so nothing here does: the update entity fills
    # itself in once the answer arrives.
    entry.async_create_background_task(
        hass, firmware.async_refresh(), f"{DOMAIN}_firmware_refresh"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
