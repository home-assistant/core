"""The Unraid integration.

This integration connects Home Assistant to Unraid servers via GraphQL API.
Provides monitoring and control for system metrics, storage, Docker, and VMs.
"""

from __future__ import annotations

from unraid_api import UnraidClient
from unraid_api.exceptions import (
    UnraidAPIError,
    UnraidAuthenticationError,
    UnraidConnectionError,
)

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT
from .coordinator import UnraidConfigEntry, UnraidRuntimeData, UnraidSystemCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid from a config entry."""
    use_ssl = entry.data.get(CONF_SSL, True)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    # Create API client with HA's shared session
    # Set both ports to user's configured port to prevent library fallback
    api_client = UnraidClient(
        host=entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
        https_port=port,
        http_port=port,
        verify_ssl=use_ssl,
        session=async_get_clientsession(hass, verify_ssl=use_ssl),
    )

    # Get server info (validates connection)
    try:
        server_info = await api_client.get_server_info()
    except UnraidAuthenticationError as err:
        raise ConfigEntryError(
            f"Authentication failed for Unraid server {entry.data[CONF_HOST]}"
        ) from err
    except (UnraidConnectionError, UnraidAPIError) as err:
        raise ConfigEntryNotReady(f"Failed to connect to Unraid server: {err}") from err

    # Create coordinator with server_info
    system_coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_info=server_info,
    )

    # Fetch initial data
    await system_coordinator.async_config_entry_first_refresh()

    # Store runtime data in config entry (HA 2024.4+ pattern)
    entry.runtime_data = UnraidRuntimeData(
        system_coordinator=system_coordinator,
        server_info=server_info,
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.system_coordinator.api_client.close()
    return unload_ok
