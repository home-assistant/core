"""Diagnostics support for the TP-Link Omada integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import OmadaConfigEntry
from .controller import OmadaSiteController
from .coordinator import OmadaCoordinator

# Only redact sensitive credentials
TO_REDACT = {CONF_PASSWORD}

# Essential device fields to include in diagnostics (max 10 per device type)
# Assumption: Focus on identity, connectivity, and firmware status
DEVICE_FIELDS = {
    "mac",
    "name",
    "type",
    "model",
    "status",
    "statusCategory",
    "ip",
    "firmwareVersion",
    "needUpgrade",
    "uptime",
}


def _flatten_omada_model(value: Any) -> Any:
    """Convert tplink-omada-client models into diagnostic-friendly data."""
    raw = getattr(value, "_data", None)
    if raw is not None:
        return raw

    if isinstance(value, dict):
        return {key: _flatten_omada_model(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_flatten_omada_model(item) for item in value]

    return value


def _extract_device_essentials(device_data: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only essential fields from a device."""
    return {
        field: device_data.get(field) for field in DEVICE_FIELDS if field in device_data
    }


def _serialize_devices_coordinator(
    coordinator: OmadaCoordinator[Any] | None,
) -> dict[str, Any] | None:
    """Serialize device coordinator with limited essential data."""
    if coordinator is None:
        return None

    return {
        "last_update_success": coordinator.last_update_success,
        "count": len(coordinator.data),
        "devices": {
            key: _extract_device_essentials(_as_dict(item))
            for key, item in coordinator.data.items()
        },
    }


def _as_dict(value: Any) -> Mapping[str, Any]:
    """Return a flattened mapping for summary calculations."""
    flattened = _flatten_omada_model(value)
    return flattened if isinstance(flattened, Mapping) else {}


def _summarize_clients(coordinator: OmadaCoordinator[Any] | None) -> dict[str, int]:
    """Return simple aggregate stats for client data."""
    if coordinator is None:
        return {
            "total": 0,
            "active": 0,
            "wireless": 0,
            "guests": 0,
        }

    total = len(coordinator.data)
    active = 0
    wireless = 0
    guests = 0

    for client in coordinator.data.values():
        data = _as_dict(client)
        if data.get("active"):
            active += 1
        if data.get("wireless"):
            wireless += 1
        if data.get("guest"):
            guests += 1

    return {
        "total": total,
        "active": active,
        "wireless": wireless,
        "guests": guests,
    }


def _get_port_status(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a normalized mapping for a port's status."""
    status = data.get("portStatus") or data.get("port_status")
    if isinstance(status, Mapping):
        return status
    return {}


def _summarize_device_ports(
    coordinators: Mapping[str, OmadaCoordinator[Any]],
) -> dict[str, dict[str, float | int]]:
    """Return per-device aggregate stats for device port data."""
    result: dict[str, dict[str, float | int]] = {}

    for switch_mac, coordinator in coordinators.items():
        total_ports = 0
        ports_up = 0
        poe_capable = 0
        poe_active = 0
        poe_power = 0.0

        for port in coordinator.data.values():
            port_data = _as_dict(port)
            total_ports += 1

            status = _get_port_status(port_data)
            link = status.get("linkStatus")
            if link is None:
                link = status.get("link_status")
            if link == 1:
                ports_up += 1

            if port_data.get("poe") in (1, True):
                poe_capable += 1

            # Try to get and convert PoE power value (using str() to satisfy mypy)
            try:
                power_value = status.get("poePower") or status.get("poe_power")
                power = float(str(power_value)) if power_value else 0.0
                if power > 0:
                    poe_active += 1
                    poe_power += power
            except (TypeError, ValueError):
                pass  # Skip invalid power values

        result[switch_mac] = {
            "total_ports": total_ports,
            "ports_up": ports_up,
            "ports_down": max(total_ports - ports_up, 0),
            "poe_capable": poe_capable,
            "poe_active": poe_active,
            "poe_power_w": round(poe_power, 2),
        }

    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    omada_entry = cast(OmadaConfigEntry, entry)
    diagnostics: dict[str, Any] = {
        "config_entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        }
    }

    controller: OmadaSiteController | None = omada_entry.runtime_data
    if controller is None:
        return async_redact_data(diagnostics, TO_REDACT)

    diagnostics["controller"] = {
        "devices": _serialize_devices_coordinator(controller.devices_coordinator),
        "clients_summary": _summarize_clients(controller.clients_coordinator),
        "device_ports_summary": _summarize_device_ports(
            controller.switch_port_coordinator_map
        ),
    }

    return async_redact_data(diagnostics, TO_REDACT)
