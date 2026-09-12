"""The KEBA P40 integration."""

from keba_kecontact_p40 import KebaP40Client

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import KebaP40ConfigEntry, KebaP40DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: KebaP40ConfigEntry) -> bool:
    """Set up KEBA P40 from a config entry."""
    client = KebaP40Client(
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass, verify_ssl=False),
        port=entry.data[CONF_PORT],
    )
    assert entry.unique_id is not None
    coordinator = KebaP40DataUpdateCoordinator(hass, entry, client, entry.unique_id)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KebaP40ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
