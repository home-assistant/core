"""The Unraid integration.

This integration connects Home Assistant to Unraid servers via GraphQL API.
Provides monitoring and control for system metrics, storage, Docker, and VMs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from unraid_api import UnraidClient
from unraid_api.exceptions import (
    UnraidAPIError,
    UnraidAuthenticationError,
    UnraidConnectionError,
)

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_HTTP_PORT,
    CONF_HTTPS_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
)
from .coordinator import UnraidConfigEntry, UnraidRuntimeData, UnraidSystemCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid from a config entry."""
    host = entry.data[CONF_HOST]
    http_port = entry.data.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)
    https_port = entry.data.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT)
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    # Get HA's aiohttp session for proper connection pooling
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    # Create API client with injected session
    api_client = UnraidClient(
        host=host,
        http_port=http_port,
        https_port=https_port,
        api_key=api_key,
        verify_ssl=verify_ssl,
        session=session,
    )

    # Test connection and get server info
    try:
        await api_client.test_connection()
        server_info = await api_client.get_server_info()
    except UnraidAuthenticationError as err:
        msg = f"Authentication failed for Unraid server {host}"
        raise ConfigEntryAuthFailed(msg) from err
    except (UnraidConnectionError, UnraidAPIError) as err:
        msg = f"Failed to connect to Unraid server: {err}"
        raise ConfigEntryNotReady(msg) from err

    server_name = server_info.hostname or host

    # Create coordinator with fixed poll interval
    system_coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_name=server_name,
    )

    # Fetch initial data
    await system_coordinator.async_config_entry_first_refresh()

    # Store runtime data in config entry (HA 2024.4+ pattern)
    entry.runtime_data = UnraidRuntimeData(
        api_client=api_client,
        system_coordinator=system_coordinator,
        server_info=server_info,
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
