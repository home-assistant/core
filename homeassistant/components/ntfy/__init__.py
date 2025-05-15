"""The ntfy integration."""

from __future__ import annotations

import logging

from aiontfy import Ntfy
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyHTTPError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.NOTIFY]


type NtfyConfigEntry = ConfigEntry[Ntfy]


async def async_setup_entry(hass: HomeAssistant, entry: NtfyConfigEntry) -> bool:
    """Set up ntfy from a config entry."""

    session = async_get_clientsession(hass, entry.data.get(CONF_VERIFY_SSL, True))
    ntfy = Ntfy(entry.data[CONF_URL], session, token=entry.data.get(CONF_TOKEN))

    try:
        await ntfy.account()
    except NtfyUnauthorizedAuthenticationError as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from e
    except NtfyHTTPError as e:
        _LOGGER.debug("Error %s: %s [%s]", e.code, e.error, e.link)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="server_error",
            translation_placeholders={"error_msg": str(e.error)},
        ) from e
    except NtfyConnectionError as e:
        _LOGGER.debug("Error", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from e
    except NtfyTimeoutError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout_error",
        ) from e

    entry.runtime_data = ntfy

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: NtfyConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NtfyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
