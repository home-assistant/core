"""Integration for Hetzner Cloud."""

from __future__ import annotations

from hcloud import APIException, Client

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import HetznerConfigEntry, HetznerCoordinator, HetznerData

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HetznerConfigEntry) -> bool:
    """Set up Hetzner Cloud from a config entry."""
    client = Client(token=entry.data[CONF_API_TOKEN])

    try:
        await hass.async_add_executor_job(client.load_balancers.get_all)
    except APIException as err:
        if err.code == 401:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err.message}"
            ) from err
        raise ConfigEntryNotReady(
            f"Error connecting to Hetzner Cloud API: {err.message}"
        ) from err

    coordinator = HetznerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HetznerData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HetznerConfigEntry) -> bool:
    """Unload a Hetzner Cloud config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
