"""The Fully Kiosk Browser integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .services import async_setup_services

type FullyKioskConfigEntry = ConfigEntry[FullyKioskDataUpdateCoordinator]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Fully Kiosk Browser."""

    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: FullyKioskConfigEntry) -> bool:
    """Set up Fully Kiosk Browser from a config entry."""

    coordinator = FullyKioskDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_update_listeners()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FullyKioskConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
