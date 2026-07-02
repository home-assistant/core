"""Diagnostics support for the Habitron integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import HabitronConfigEntry

REDACT_KEYS = {
    "websock_token",
    "mac",
    "lan mac",
    "serial",
}


def _module_summary(module: Any) -> dict[str, Any]:
    """Return a JSON-friendly snapshot of a single Habitron module."""
    return {
        "uid": getattr(module, "uid", None),
        "name": getattr(module, "name", None),
        "type": (
            module.typ.hex()
            if isinstance(getattr(module, "typ", None), bytes)
            else None
        ),
        "mod_type": getattr(module, "mod_type", None),
        "addr": getattr(module, "addr", None),
        "sw_version": getattr(module, "sw_version", None),
        "input_count": len(getattr(module, "inputs", []) or []),
        "output_count": len(getattr(module, "outputs", []) or []),
        "sensor_count": len(getattr(module, "sensors", []) or []),
        "led_count": len(getattr(module, "leds", []) or []),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HabitronConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the given Habitron config entry."""
    smhub = entry.runtime_data
    router = smhub.router
    coordinator = smhub.coordinator

    return {
        "config_entry": {
            "data": async_redact_data(dict(entry.data), REDACT_KEYS),
            "options": async_redact_data(dict(entry.options), REDACT_KEYS),
            "unique_id": entry.unique_id,
            "title": entry.title,
        },
        "hub": {
            "uid": smhub.uid,
            "version": smhub.smhub_version,
            "type": smhub.smhub_type,
            "host": smhub.host,
            "addon_slug": smhub.addon_slug,
            "online": smhub.online,
        },
        "router": {
            "uid": router.uid,
            "id": router.id,
            "name": router.name,
            "version": router.version,
            "sys_ok": router.sys_ok,
            "module_count": len(router.modules),
            "area_count": len(router.areas),
            "max_group": router.max_group,
        },
        "coordinator": {
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "last_update_success": coordinator.last_update_success,
            "always_update": coordinator.always_update,
        },
        "modules": [_module_summary(m) for m in router.modules],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a single Habitron device (module or hub)."""
    smhub = entry.runtime_data
    router = smhub.router

    # Map the device's domain identifier back to a Habitron uid.
    target_uid: str | None = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
        None,
    )

    target: dict[str, Any] | None = None
    if target_uid == smhub.uid:
        target = {
            "kind": "hub",
            "summary": {"uid": smhub.uid, "name": smhub.smhub_name},
        }
    elif target_uid == router.uid:
        target = {"kind": "router", "summary": {"uid": router.uid, "name": router.name}}
    else:
        for module in router.modules:
            if getattr(module, "uid", None) == target_uid:
                target = {"kind": "module", "summary": _module_summary(module)}
                break

    return {
        "device_identifier": target_uid,
        "device_name": device.name,
        "device_model": device.model,
        "device_sw_version": device.sw_version,
        "target": target,
    }
