"""Integration diagnostics."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MillDataCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Provide diagnostics for the Mill WiFi config entry."""
    mill_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MillDataCoordinator = mill_data["coordinator"]
    api = mill_data["api"]

    diagnostics_data = {
        "entry_id": entry.entry_id,
        "username": api.username,
        "device_count": 0,
        "devices": [],
        "coordinator_last_update_success": coordinator.last_update_success,
        "coordinator_data_present": coordinator.data is not None,
    }

    if coordinator.data:
        diagnostics_data["device_count"] = len(coordinator.data)
        for device_id, device_details in coordinator.data.items():
            if not isinstance(device_details, dict):
                diagnostics_data["devices"].append(
                    {
                        "deviceId": device_id,
                        "error": "Device data is not a dictionary.",
                        "data_type": str(type(device_details)),
                    }
                )
                continue

            diagnostics_data["devices"].append(
                {
                    "deviceId": device_details.get("deviceId"),
                    "customName": device_details.get("customName"),
                    "type": device_details.get("deviceType", {})
                    .get("childType", {})
                    .get("name"),
                    "isConnected": device_details.get("isConnected"),
                    "isEnabled": device_details.get("isEnabled"),
                    "metrics": device_details.get("lastMetrics", {}),
                    "settings_reported": device_details.get("deviceSettings", {}).get(
                        "reported", {}
                    ),
                }
            )
    else:
        diagnostics_data["message"] = "Coordinator data is empty or not yet available."

    return diagnostics_data
