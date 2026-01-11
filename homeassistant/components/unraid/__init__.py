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
from unraid_api.models import ServerInfo

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import (
    CONF_HTTP_PORT,
    CONF_HTTPS_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
)
from .const import DEFAULT_STORAGE_POLL_INTERVAL, DEFAULT_SYSTEM_POLL_INTERVAL, DOMAIN
from .coordinator import (
    UnraidConfigEntry,
    UnraidRuntimeData,
    UnraidStorageCoordinator,
    UnraidSystemCoordinator,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

__all__ = [
    "DOMAIN",
    "PLATFORMS",
    "ServerInfo",
    "UnraidConfigEntry",
    "UnraidRuntimeData",
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
        await api_client.close()
        msg = f"Authentication failed for Unraid server {host}"
        raise ConfigEntryAuthFailed(msg) from err
    except (UnraidConnectionError, UnraidAPIError) as err:
        await api_client.close()
        msg = f"Failed to connect to Unraid server: {err}"
        raise ConfigEntryNotReady(msg) from err

    server_name = server_info.hostname or host

    # Create coordinators with fixed poll intervals
    system_coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_name=server_name,
        update_interval=DEFAULT_SYSTEM_POLL_INTERVAL,
    )

    storage_coordinator = UnraidStorageCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_name=server_name,
        update_interval=DEFAULT_STORAGE_POLL_INTERVAL,
    )

    # Fetch initial data
    await system_coordinator.async_config_entry_first_refresh()
    await storage_coordinator.async_config_entry_first_refresh()

    # Store runtime data in config entry (HA 2024.4+ pattern)
    entry.runtime_data = UnraidRuntimeData(
        api_client=api_client,
        system_coordinator=system_coordinator,
        storage_coordinator=storage_coordinator,
        server_info=server_info,
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.api_client.close()

    return unload_ok
