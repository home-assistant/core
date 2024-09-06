"""The emoncms component."""

from pyemoncms import EmoncmsClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import EmoncmsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EmonCMSConfigEntry = ConfigEntry[EmoncmsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EmonCMSConfigEntry) -> bool:
    """Load a config entry."""
    emoncms_client = EmoncmsClient(
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    coordinator = EmoncmsCoordinator(hass, emoncms_client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
