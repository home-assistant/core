"""Snapcast Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import SnapcastUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snapcast from a config entry."""
    coordinator = SnapcastUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except OSError as ex:
        raise ConfigEntryNotReady(
            "Could not connect to Snapcast server at "
            f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        snapcast_data = hass.data[DOMAIN].pop(entry.entry_id)
        # disconnect from server
        await snapcast_data.disconnect()
    return unload_ok
