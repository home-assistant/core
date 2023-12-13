"""The swiss_public_transport component."""
import logging

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant import config_entries, core
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DESTINATION, CONF_START, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    config = entry.data
    hass.data.setdefault(DOMAIN, {})

    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    session = async_get_clientsession(hass)
    opendata = OpendataTransport(start, destination, session)

    try:
        await opendata.async_get_data()
    except OpendataTransportConnectionError as e:
        raise ConfigEntryNotReady(
            f"Timeout while connecting for entry '{start} {destination}'"
        ) from e
    except OpendataTransportError as e:
        _LOGGER.error(
            "Setup failed for entry '%s %s', check at http://transport.opendata.ch/examples/stationboard.html if your station names are valid",
            start,
            destination,
        )
        raise ConfigEntryError(
            f"Setup failed for entry '{start} {destination}' with invalid data"
        ) from e

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
