"""The Prosegur Alarm integration."""

import logging

from pyprosegur.auth import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.CAMERA]

type ProsegurConfigEntry = ConfigEntry[Auth]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ProsegurConfigEntry) -> bool:
    """Set up Prosegur Alarm from a config entry."""
    try:
        session = aiohttp_client.async_get_clientsession(hass)
        auth = Auth(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_COUNTRY],
        )
        await auth.login()

    except ConnectionRefusedError as error:
        _LOGGER.error("Configured credential are invalid, %s", error)

        raise ConfigEntryAuthFailed from error

    except ConnectionError as error:
        _LOGGER.error("Could not connect with Prosegur backend: %s", error)
        raise ConfigEntryNotReady from error

    entry.runtime_data = auth

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProsegurConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
