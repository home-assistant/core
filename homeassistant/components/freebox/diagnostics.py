"""Diagnostics support for Freebox."""

from typing import Any

from homeassistant.core import HomeAssistant

from .router import FreeboxConfigEntry

STORAGE_KEYS_TO_OMIT = {
    "dev_uuid",
    "label",
    "name",
    "path",
    "serial",
    "set_name",
    "set_uuid",
    "uuid",
}
HOME_ENDPOINTS_TO_OMIT = {"disk", "pin"}


def _omit(data: Any, keys: set[str]) -> Any:
    """Return data without the given keys, recursively."""
    if isinstance(data, dict):
        return {k: _omit(v, keys) for k, v in data.items() if k not in keys}
    if isinstance(data, list):
        return [_omit(item, keys) for item in data]
    return data


def _home_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return the debugging relevant part of a home node."""
    return {
        "id": node["id"],
        "category": node["category"],
        "type": node.get("type", {}).get("name"),
        "status": node.get("status"),
        "firmware_version": (node.get("props") or {}).get("FwVersion"),
        "endpoints": [
            {
                "id": endpoint["id"],
                "name": endpoint["name"],
                "ep_type": endpoint["ep_type"],
                "value_type": endpoint.get("value_type"),
                "value": endpoint.get("value"),
            }
            for endpoint in node.get("show_endpoints", [])
            # Alarm PIN code and camera recording volume label
            if endpoint["name"] not in HOME_ENDPOINTS_TO_OMIT
        ],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FreeboxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    router = entry.runtime_data
    device_info = router.device_info
    return {
        "router": {
            "model": device_info.get("model"),
            "model_id": device_info.get("model_id"),
            "sw_version": device_info.get("sw_version"),
            "hw_version": device_info.get("hw_version"),
            "supports_hosts": router.supports_hosts,
            "supports_raid": router.supports_raid,
            "home_granted": router.home_granted,
            "tracked_devices": len(router.devices),
            "calls": len(router.call_list),
        },
        "sensors": router.sensors,
        "disks": _omit(list(router.disks.values()), STORAGE_KEYS_TO_OMIT),
        "raids": _omit(list(router.raids.values()), STORAGE_KEYS_TO_OMIT),
        "home_devices": [_home_node(node) for node in router.home_devices.values()],
    }
