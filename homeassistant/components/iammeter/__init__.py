"""IAMMETER integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IammeterConfigEntry, IammeterDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
    """Set up IAMMETER from a config entry."""
    coordinator = IammeterDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
    """Unload an IAMMETER config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
