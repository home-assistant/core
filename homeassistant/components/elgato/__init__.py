"""Support for Elgato Key Lights."""
import logging

from elgato import Elgato, ElgatoConnectionError

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ELGATO_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Elgato Key Light components."""
    return True


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
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_ELGATO_CLIENT: elgato}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, LIGHT_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Elgato Key Light config entry."""
    # Unload entities for this entry/device.
    await hass.config_entries.async_forward_entry_unload(entry, LIGHT_DOMAIN)

    # Cleanup
    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
