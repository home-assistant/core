"""Diagnostics support for System Bridge."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import SystemBridgeConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_HOST,
    CONF_TOKEN,
    "address",
    "album_artist",
    "album_title",
    "artist",
    "broadcast",
    "camera_usage",
    "device",
    "discovery_keys",
    "fqdn",
    "hostname",
    "ip_address_4",
    "ip_address_6",
    "mac_address",
    "microphone_usage",
    "mount_point",
    "ptp",
    "ssid",
    "subtitle",
    "thumbnail",
    "title",
    "unique_id",
    "users",
    "uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SystemBridgeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = asdict(coordinator.data)
    # The process and connection lists are long and say a lot about the user
    data.pop("processes")
    if data["networks"] is not None:
        data["networks"].pop("connections")
        # Interface names such as enx001122aabbcc can hold the MAC address
        data["networks"] = async_redact_data(data["networks"], {"name"})
    if data["battery"] is not None:
        # Bluetooth battery names such as hid-AA:BB:CC:DD:EE:FF-battery hold the MAC
        data["battery"] = async_redact_data(data["battery"], {"name"})
    if data["disks"] is not None:
        # Disks are named after their device path, and mount options can hold paths
        data["disks"] = async_redact_data(data["disks"], {"name", "options"})
    if data["system"] is not None and data["system"]["failed_units"] is not None:
        # Unit names and descriptions can hold paths, such as for mount units
        data["system"]["failed_units"] = async_redact_data(
            data["system"]["failed_units"], {"description", "name"}
        )

    listen_task = coordinator.listen_task
    last_exception = coordinator.last_exception

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "connection": {
            "websocket_connected": coordinator.websocket_client.connected,
            "listening": listen_task is not None and not listen_task.done(),
            # The message can contain the host, so only the type is kept
            "last_exception": (
                type(last_exception).__name__ if last_exception else None
            ),
        },
        "data": async_redact_data(data, TO_REDACT),
    }
