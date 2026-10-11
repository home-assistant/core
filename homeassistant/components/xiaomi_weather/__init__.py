"""The Xiaomi Weather integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import XiaomiWeatherConfigEntry, XiaomiWeatherCoordinator

PLATFORMS = [Platform.WEATHER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant, entry: XiaomiWeatherConfigEntry
) -> bool:
    """Fetch initial data before setting up platforms."""
    coordinator = XiaomiWeatherCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XiaomiWeatherConfigEntry
) -> bool:
    """Unload entities and their coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
