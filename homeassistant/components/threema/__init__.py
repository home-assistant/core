"""The Threema Gateway integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .client import ThreemaAPIClient, ThreemaAuthError, ThreemaConnectionError
from .const import CONF_API_SECRET, CONF_GATEWAY_ID, CONF_PRIVATE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.IMAGE, Platform.NOTIFY]

type ThreemaConfigEntry = ConfigEntry[ThreemaAPIClient]


async def async_setup_entry(hass: HomeAssistant, entry: ThreemaConfigEntry) -> bool:
    """Set up Threema Gateway from a config entry."""
    client = ThreemaAPIClient(
        hass,
        gateway_id=entry.data[CONF_GATEWAY_ID],
        api_secret=entry.data[CONF_API_SECRET],
        private_key=entry.data.get(CONF_PRIVATE_KEY),
    )

    try:
        await client.validate_credentials()
    except ThreemaAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except ThreemaConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThreemaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
