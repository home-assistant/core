"""The Smart Meter B Route integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .coordinator import BRouteUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type BRouteConfigEntry = ConfigEntry[BRouteUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Set up Smart Meter B Route from a config entry."""

    device = entry.data[CONF_DEVICE]
    bid = entry.data[CONF_ID]
    password = entry.data[CONF_PASSWORD]
    coordinator = BRouteUpdateCoordinator(hass, device, bid, password)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
