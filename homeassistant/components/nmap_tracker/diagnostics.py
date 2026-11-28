"""Diagnostics support for Nmap Tracker."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EXCLUDE
from homeassistant.core import HomeAssistant

from . import NmapTrackerConfigEntry
from .const import CONF_HOSTS_EXCLUDE, CONF_MAC_EXCLUDE

# The scanned ranges stay visible to check that a device's subnet is covered
TO_REDACT = {CONF_EXCLUDE, CONF_HOSTS_EXCLUDE, CONF_MAC_EXCLUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NmapTrackerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    devices = entry.runtime_data.devices
    # Tracked devices are shared by all config entries
    entry_devices = [
        device
        for mac_address, device in devices.tracked.items()
        if devices.config_entry_owner.get(mac_address) == entry.entry_id
    ]
    return {
        "options": async_redact_data(entry.options, TO_REDACT),
        "tracked_devices": len(entry_devices),
        "offline_devices": sum(
            device.first_offline is not None for device in entry_devices
        ),
    }
