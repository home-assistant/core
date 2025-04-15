"""Vodafone Station integration."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VodafoneConfigEntry, VodafoneStationRouter

PLATFORMS = [Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VodafoneConfigEntry) -> bool:
    """Set up Vodafone Station platform."""
    coordinator = VodafoneStationRouter(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VodafoneConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: VodafoneConfigEntry) -> None:
    """Update when config_entry options update."""
    if entry.options:
        await hass.config_entries.async_reload(entry.entry_id)
