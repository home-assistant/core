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
    # Not a first refresh: a light on the local network has no business
    # failing to set up because Elgato's servers are having a day.
    await firmware.async_refresh()

    entry.runtime_data = ElgatoCoordinators(device=coordinator, firmware=firmware)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
