"""The swiss_public_transport component."""
import logging

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import OpendataTransportError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_DESTINATION, CONF_START, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_START): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
    }
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    config = entry.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = config

    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    session = async_get_clientsession(hass)
    opendata = OpendataTransport(start, destination, session)

    try:
        await opendata.async_get_data()
    except OpendataTransportError:
        _LOGGER.error(
            "Check at http://transport.opendata.ch/examples/stationboard.html "
            "if your station names are valid"
        )
        return False

    hass.data[DOMAIN][f"{entry.entry_id}_opendata_client"] = opendata

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
