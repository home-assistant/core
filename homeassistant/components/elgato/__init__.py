"""Support for Elgato Key Lights."""
import logging

from elgato import Elgato, ElgatoConnectionError

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_ELGATO_CLIENT, DOMAIN

PLATFORMS = [LIGHT_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elgato Key Light from a config entry."""
    session = async_get_clientsession(hass)
    elgato = Elgato(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=session,
    )

    # Ensure we can connect to it
    try:
        await elgato.info()
    except ElgatoConnectionError as exception:
        logging.getLogger(__name__).debug("Unable to connect: %s", exception)
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_ELGATO_CLIENT: elgato}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Elgato Key Light config entry."""
    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
