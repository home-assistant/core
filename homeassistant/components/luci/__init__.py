"""The luci component."""

from __future__ import annotations

from openwrt_luci_rpc import OpenWrtRpc
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, PLATFORMS
from .coordinator import LuciConfigEntry, LuciCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: LuciConfigEntry) -> bool:
    """Set up OpenWrt (luci) from a config entry."""
    try:
        router = await hass.async_add_executor_job(
            OpenWrtRpc,
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_SSL, DEFAULT_SSL),
            entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
    except (ConnectionError, RequestsConnectionError) as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to router at {entry.data[CONF_HOST]}"
        ) from err

    if not await hass.async_add_executor_job(router.is_logged_in):
        raise ConfigEntryAuthFailed("Invalid credentials for router")

    coordinator = LuciCoordinator(hass, entry, router)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LuciConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
