"""FortiOS Device Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

from .coordinator import FortiOSDataUpdateCoordinator
from .firewall import FortiOSAPI

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

type FortiOSConfigEntry = ConfigEntry[FortiOSDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FortiOSConfigEntry) -> bool:
    """Set up FortiOS from a config entry."""
    api = FortiOSAPI(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
        entry.data["vdom"],
        entry.data[CONF_VERIFY_SSL],
    )

    coordinator = FortiOSDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FortiOSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
