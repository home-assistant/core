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

from .config_flow import (
    CONF_HTTP_PORT,
    CONF_HTTPS_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
)
from .const import (
    CONF_STORAGE_INTERVAL,
    CONF_SYSTEM_INTERVAL,
    DEFAULT_STORAGE_POLL_INTERVAL,
    DEFAULT_SYSTEM_POLL_INTERVAL,
    DOMAIN,
)
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

# Re-export for external use
__all__ = ["DOMAIN", "UnraidConfigEntry", "UnraidRuntimeData"]


def _build_server_info(info: dict, host: str, verify_ssl: bool) -> dict:
    """Build server info dictionary from API response."""
    info_data = info.get("info", {})
    system_data = info_data.get("system", {})
    baseboard_data = info_data.get("baseboard", {})
    os_data = info_data.get("os", {})
    cpu_data = info_data.get("cpu", {})
    versions_data = info_data.get("versions", {}).get("core", {})
    server_data = info.get("server", {})
    registration_data = info.get("registration", {})

    # Use Lime Technology as manufacturer (Unraid vendor)
    manufacturer = "Lime Technology"

    # Model shows "Unraid {version}" for prominent display in Device Info
    unraid_version = versions_data.get("unraid", "Unknown")
    model = f"Unraid {unraid_version}"

    # Store hardware info separately for diagnostics/attributes
    hw_manufacturer = system_data.get("manufacturer") or baseboard_data.get(
        "manufacturer"
    )
    hw_model = system_data.get("model") or baseboard_data.get("model")
    serial_number = system_data.get("serial") or baseboard_data.get("serial") or None

    server_name = os_data.get("hostname") or host
    server_uuid = system_data.get("uuid")

    # Determine configuration URL for device info
    configuration_url = server_data.get("localurl")
    if not configuration_url:
        lan_ip = server_data.get("lanip")
        if lan_ip:
            protocol = "https" if verify_ssl else "http"
            configuration_url = f"{protocol}://{lan_ip}"

    return {
        "uuid": server_uuid,
        "name": server_name,
        "manufacturer": manufacturer,
        "model": model,
        "serial_number": serial_number,
        "sw_version": unraid_version,
        "hw_version": os_data.get("kernel"),
        "os_distro": os_data.get("distro"),
        "os_release": os_data.get("release"),
        "os_arch": os_data.get("arch"),
        "api_version": versions_data.get("api"),
        "license_type": registration_data.get("type"),
        "lan_ip": server_data.get("lanip"),
        "configuration_url": configuration_url,
        "cpu_brand": cpu_data.get("brand"),
        "cpu_cores": cpu_data.get("cores"),
        "cpu_threads": cpu_data.get("threads"),
        # Hardware info for diagnostics
        "hw_manufacturer": hw_manufacturer,
        "hw_model": hw_model,
    }


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid from a config entry."""
    host = entry.data[CONF_HOST]
    http_port = entry.data.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)
    https_port = entry.data.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT)
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    # Get polling intervals from options (or use defaults)
    system_interval = entry.options.get(
        CONF_SYSTEM_INTERVAL, DEFAULT_SYSTEM_POLL_INTERVAL
    )
    storage_interval = entry.options.get(
        CONF_STORAGE_INTERVAL, DEFAULT_STORAGE_POLL_INTERVAL
    )

    # Get HA's aiohttp session for proper connection pooling
    # Use verify_ssl=False session if user disabled SSL verification
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
        info = await api_client.query(
            """
            query SystemInfo {
                info {
                    system { uuid manufacturer model serial }
                    baseboard { manufacturer model serial }
                    os { hostname distro release kernel arch }
                    cpu { manufacturer brand cores threads }
                    versions { core { unraid api } }
                }
                server { lanip localurl remoteurl }
                registration { type state }
            }
            """
        )
    except UnraidAuthenticationError as err:
        await api_client.close()
        msg = f"Authentication failed for Unraid server {host}"
        raise ConfigEntryAuthFailed(msg) from err
    except (UnraidConnectionError, UnraidAPIError) as err:
        await api_client.close()
        msg = f"Failed to connect to Unraid server: {err}"
        raise ConfigEntryNotReady(msg) from err

    # Build server info using helper function
    server_info = _build_server_info(info, host, verify_ssl)
    server_name = server_info["name"]

    # Create coordinators
    system_coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_name=server_name,
        update_interval=system_interval,
    )

    storage_coordinator = UnraidStorageCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        server_name=server_name,
        update_interval=storage_interval,
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

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_options_update_listener))

    _LOGGER.info(
        "Unraid integration setup complete for %s (system: %ds, storage: %ds)",
        server_name,
        system_interval,
        storage_interval,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close API client
        await entry.runtime_data.api_client.close()
        _LOGGER.info("Unraid integration unloaded for entry %s", entry.title)

    return unload_ok


async def _async_options_update_listener(
    hass: HomeAssistant, entry: UnraidConfigEntry
) -> None:
    """Handle options update - triggers full entry reload."""
    _LOGGER.info(
        "Options changed for %s, reloading integration",
        entry.title,
    )
    # Reload the entry to apply new options
    await hass.config_entries.async_reload(entry.entry_id)
