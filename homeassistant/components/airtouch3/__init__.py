"""The AirTouch 3 Air Conditioner integration."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import AirTouch3ConfigEntry, Airtouch3DataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Set up AirTouch 3 Air Conditioner from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, host)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
