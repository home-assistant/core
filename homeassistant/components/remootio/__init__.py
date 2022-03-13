"""The Remootio integration."""
from __future__ import annotations

import logging

from aioremootio import ConnectionOptions, RemootioClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    REMOOTIO_CLIENT,
)
from .utils import create_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remootio from a config entry."""

    _LOGGER.debug("entry [%s]", entry.as_dict())

    connection_options: ConnectionOptions = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_API_SECRET_KEY],
        entry.data[CONF_API_AUTH_KEY],
    )
    serial_number: str = entry.data[CONF_SERIAL_NUMBER]

    remootio_client: RemootioClient = await create_client(
        hass, connection_options, _LOGGER, serial_number
    )

    hass_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    hass_data[REMOOTIO_CLIENT] = remootio_client

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
