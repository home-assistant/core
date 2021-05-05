"""The Prosegur Alarm integration."""
import asyncio
import logging

from pyprosegur.auth import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_COUNTRY, DOMAIN

PLATFORMS = ["alarm_control_panel"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Prosegur Alarm from a config entry."""
    try:
        session = aiohttp_client.async_get_clientsession(hass)
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = Auth(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_COUNTRY],
        )
        await hass.data[DOMAIN][entry.entry_id].login()

        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )

        return True
    except ConnectionRefusedError:
        _LOGGER.error("Configured credential are invalid, please reconfigure")
    except ConnectionError as error:
        _LOGGER.error("Could not connect with Prosegur backend: %s", error)
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
