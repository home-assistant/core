"""The mill component."""
from mill import Mill

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = ["climate", "sensor"]


async def async_setup_entry(hass, entry):
    """Set up the Mill heater."""
    mill_data_connection = Mill(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )
    if not await mill_data_connection.connect():
        raise ConfigEntryNotReady

    await mill_data_connection.find_all_heaters()

    hass.data[DOMAIN] = mill_data_connection

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
