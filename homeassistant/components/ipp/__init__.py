"""The Internet Printing Protocol (IPP) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_PATH
from .coordinator import IPPDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

type IPPConfigEntry = ConfigEntry[IPPDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IPPConfigEntry) -> bool:
    """Set up IPP from a config entry."""
    # config flow sets this to either UUID, serial number or None
    if (device_id := entry.unique_id) is None:
        device_id = entry.entry_id

    coordinator = IPPDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        base_path=entry.data[CONF_BASE_PATH],
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        device_id=device_id,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
