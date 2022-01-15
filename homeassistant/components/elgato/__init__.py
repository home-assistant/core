"""Support for Elgato Lights."""
import logging
from typing import NamedTuple

from elgato import Elgato, ElgatoConnectionError, Info

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = [Platform.BUTTON, Platform.LIGHT]


class HomeAssistantElgatoData(NamedTuple):
    """Elgato data stored in the Home Assistant data object."""

    client: Elgato
    info: Info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elgato Light from a config entry."""
    session = async_get_clientsession(hass)
    elgato = Elgato(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=session,
    )

    # Ensure we can connect to it
    try:
        info = await elgato.info()
    except ElgatoConnectionError as exception:
        logging.getLogger(__name__).debug("Unable to connect: %s", exception)
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantElgatoData(
        client=elgato,
        info=info,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
