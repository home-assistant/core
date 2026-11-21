"""Diagnostics support for YoLink."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import YoLinkConfigEntry

# Keys in the device state reports that identify a device, the home, the local
# network, or the time zone (a hint at the location).
TO_REDACT = {
    "deviceId",
    "gateway",
    "gatewayId",
    "ip",
    "mac",
    "mask",
    "name",
    "netId",
    "parentDeviceId",
    "sn",
    "ssid",
    "token",
    "tz",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YoLinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # The OAuth token, the home ID, device IDs, device tokens, and device names
    # are left out, as they identify the account and its devices. Devices are a
    # list instead of a mapping keyed by device ID for the same reason.
    return {
        "devices": [
            {
                "type": coordinator.device.device_type,
                "model": coordinator.device.device_model_name,
                "online": coordinator.dev_online,
                "net_type": coordinator.dev_net_type,
                "paired": coordinator.paired_device is not None,
                "last_update_success": coordinator.last_update_success,
                "state": async_redact_data(coordinator.data, TO_REDACT),
            }
            for coordinator in entry.runtime_data.device_coordinators.values()
        ],
    }
