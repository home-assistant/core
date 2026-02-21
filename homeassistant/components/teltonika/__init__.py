"""The Teltonika integration."""

from __future__ import annotations

import logging

from teltasync import Teltasync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TeltonikaDataUpdateCoordinator
from .util import normalize_url

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type TeltonikaConfigEntry = ConfigEntry[TeltonikaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Set up Teltonika from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    validate_ssl = entry.data.get(CONF_VERIFY_SSL, False)
    session = async_get_clientsession(hass)

    base_url = normalize_url(host)

    client = Teltasync(
        base_url=f"{base_url}/api",
        username=username,
        password=password,
        session=session,
        verify_ssl=validate_ssl,
    )

    # Create coordinator
    coordinator = TeltonikaDataUpdateCoordinator(hass, client, entry, base_url)

    # Fetch initial data and set up device info
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.device_info is not None

    # Store runtime data
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()

    return unload_ok
