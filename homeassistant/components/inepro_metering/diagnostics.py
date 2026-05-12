"""Diagnostics support for Inepro Metering."""

from datetime import datetime
from typing import Any

from inepro_metering.runtime import MeterRuntimeData

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import CONF_PASSWORD, CONF_SSID
from .const import CONF_METERS, CONF_SERIAL_NUMBER, CONF_TRANSPORT
from .coordinator import CoordinatorData, SerialBusCoordinatorData
from .entry_data import (
    ConfiguredMeter,
    ConfiguredRoute,
    build_meter_key,
    build_route_key,
    get_active_route,
    get_active_route_for_meter,
    get_configured_meters,
    get_configured_routes,
    get_meter_routes,
    is_bus_entry,
    serialize_configured_route,
)

_REDACT_KEYS = {
    CONF_PASSWORD,
    CONF_SSID,
    "pairing_code",
    "pairing_pin",
    "pin",
    "secret",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for one config entry."""
    del hass
    coordinator = getattr(config_entry, "runtime_data", None)
    return {
        "entry": {
            "title": config_entry.title,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
            "version": config_entry.version,
            "minor_version": config_entry.minor_version,
            "data": async_redact_data(dict(config_entry.data), _REDACT_KEYS),
            "options": async_redact_data(dict(config_entry.options), _REDACT_KEYS),
        },
        "transport": _build_transport_diagnostics(config_entry),
        "runtime": _build_runtime_diagnostics(config_entry, coordinator),
        "coordinator": _build_coordinator_diagnostics(coordinator),
    }


def _build_transport_diagnostics(config_entry: ConfigEntry) -> dict[str, Any]:
    """Return safe route and transport metadata for one entry."""
    entry_data = dict(config_entry.data)
    diagnostics: dict[str, Any] = {
        "entry_transport": entry_data[CONF_TRANSPORT],
        "bus_entry": is_bus_entry(entry_data),
        "entry_endpoint": _transport_endpoint(entry_data),
    }

    if CONF_METERS in entry_data:
        diagnostics["meters"] = [
            _build_meter_route_diagnostics(meter, bus_entry_data=entry_data)
            for meter in get_configured_meters(entry_data, title=config_entry.title)
        ]
        return diagnostics

    active_route = get_active_route(entry_data)
    diagnostics["active_route_key"] = build_route_key(active_route)
    diagnostics["active_route"] = _serialize_route(active_route)
    diagnostics["available_routes"] = [
        _serialize_route(route) for route in get_configured_routes(entry_data)
    ]
    return diagnostics


def _build_meter_route_diagnostics(
    meter: ConfiguredMeter,
    *,
    bus_entry_data: dict[str, Any],
) -> dict[str, Any]:
    """Return route metadata for one configured bus meter."""
    active_route = get_active_route_for_meter(meter, bus_entry_data=bus_entry_data)
    return {
        "meter_key": build_meter_key(meter),
        "name": meter.name,
        "serial_number": meter.serial_number,
        "variant": meter.variant,
        "active_route_key": build_route_key(active_route),
        "active_route": _serialize_route(active_route),
        "available_routes": [
            _serialize_route(route)
            for route in get_meter_routes(meter, bus_entry_data=bus_entry_data)
        ],
    }


def _serialize_route(route: ConfiguredRoute) -> dict[str, Any]:
    """Return one safe serialized route with its stable key."""
    return {
        "route_key": build_route_key(route),
        **serialize_configured_route(route),
    }


def _transport_endpoint(data: dict[str, Any]) -> dict[str, Any]:
    """Return safe endpoint metadata for the entry-level transport."""
    endpoint: dict[str, Any] = {"transport": data[CONF_TRANSPORT]}
    if data[CONF_TRANSPORT] == "serial":
        endpoint["serial_port"] = data.get("serial_port")
    elif data[CONF_TRANSPORT] in {"bluetooth", "bluetooth_proxy"}:
        endpoint["bluetooth_address"] = data.get("bluetooth_address")
        endpoint["bluetooth_name"] = data.get("bluetooth_name")
        if data[CONF_TRANSPORT] == "bluetooth_proxy":
            endpoint["host"] = data.get("host")
            endpoint["port"] = data.get("port")
    else:
        endpoint["host"] = data.get("host")
        endpoint["port"] = data.get("port")

    endpoint["slave_id"] = data.get("slave_id")
    endpoint["timeout"] = data.get("timeout")
    return endpoint


def _build_runtime_diagnostics(
    config_entry: ConfigEntry,
    coordinator: Any,
) -> dict[str, Any] | None:
    """Return summary runtime data without exposing full raw readings."""
    if coordinator is None or getattr(coordinator, "data", None) is None:
        return None

    if isinstance(coordinator.data, CoordinatorData):
        return {
            "meters": [
                _summarize_runtime_meter(
                    meter_runtime=coordinator.data.meter,
                    meter_key=str(
                        config_entry.data.get(
                            CONF_SERIAL_NUMBER,
                            config_entry.title,
                        )
                    ),
                    configured_name=config_entry.title,
                )
            ]
        }

    if isinstance(coordinator.data, SerialBusCoordinatorData):
        configured_meters = get_configured_meters(
            config_entry.data, title=config_entry.title
        )
        return {
            "meters": [
                _summarize_runtime_meter(
                    meter_runtime=coordinator.data.meters[meter_key].meter,
                    meter_key=meter_key,
                    configured_name=meter.name,
                )
                for meter in configured_meters
                if (meter_key := build_meter_key(meter)) in coordinator.data.meters
            ]
        }

    return None


def _summarize_runtime_meter(
    *,
    meter_runtime: MeterRuntimeData,
    meter_key: str,
    configured_name: str,
) -> dict[str, Any]:
    """Return a contributor-friendly runtime summary for one meter."""
    return {
        "meter_key": meter_key,
        "configured_name": configured_name,
        "model": meter_runtime.profile.title,
        "family": meter_runtime.profile.family.value,
        "variant": meter_runtime.profile.variant,
        "route": {
            "transport": meter_runtime.route.transport.value,
            "slave_id": meter_runtime.route.slave_id,
        },
        "connection": {
            "available": meter_runtime.connection.available,
            "last_successful_update": _format_datetime(
                meter_runtime.connection.last_successful_update
            ),
        },
        "identity": {
            "serial_number": meter_runtime.identity.serial_number,
            "product_code": meter_runtime.identity.product_code,
            "meter_code": meter_runtime.identity.meter_code,
            "device_serial": meter_runtime.identity.device_serial,
        },
        "device_identification": {
            "manufacturer_name": meter_runtime.device_identification.manufacturer_name,
            "product_name": meter_runtime.device_identification.product_name,
            "device_version": meter_runtime.device_identification.device_version,
        },
        "firmware": {
            "software_version": meter_runtime.firmware.software_version,
            "hardware_version": meter_runtime.firmware.hardware_version,
            "device_version": meter_runtime.firmware.device_version_value,
            "legal_software_version": meter_runtime.firmware.formatted_version(
                "legal_software_version"
            ),
            "non_legal_software_version": meter_runtime.firmware.formatted_version(
                "non_legal_software_version"
            ),
        },
        "gateway": {
            "device_type": meter_runtime.gateway.device_type,
            "hardware_version": meter_runtime.gateway.hardware_version,
            "serial_number": meter_runtime.gateway.serial_number,
            "firmware_version": meter_runtime.gateway.firmware_version,
            "bootloader_version": meter_runtime.gateway.bootloader_version,
        },
        "writable_settings": sorted(meter_runtime.writable_settings),
        "readings": {
            "count": len(meter_runtime.readings),
            "keys": sorted(meter_runtime.readings),
        },
    }


def _build_coordinator_diagnostics(coordinator: Any) -> dict[str, Any] | None:
    """Return a high-level coordinator snapshot."""
    if coordinator is None:
        return None

    diagnostics: dict[str, Any] = {
        "type": coordinator.__class__.__name__,
        "has_data": getattr(coordinator, "data", None) is not None,
        "last_update_success": getattr(coordinator, "last_update_success", None),
    }

    last_exception = getattr(coordinator, "last_exception", None)
    if last_exception is not None:
        diagnostics["last_exception"] = type(last_exception).__name__

    data = getattr(coordinator, "data", None)
    if isinstance(data, CoordinatorData):
        diagnostics["snapshot"] = _build_single_meter_snapshot(data)
    elif isinstance(data, SerialBusCoordinatorData):
        diagnostics["snapshot"] = _build_bus_snapshot(data)

    return diagnostics


def _build_single_meter_snapshot(data: CoordinatorData) -> dict[str, Any]:
    """Return a light snapshot for a single-meter coordinator."""
    return {
        "meter_count": 1,
        "available": data.meter.connection.available,
        "last_successful_update": _format_datetime(
            data.meter.connection.last_successful_update
        ),
        "reading_count": len(data.meter.readings),
    }


def _build_bus_snapshot(data: SerialBusCoordinatorData) -> dict[str, Any]:
    """Return a light snapshot for a shared-bus coordinator."""
    return {
        "meter_count": len(data.meters),
        "available_meters": sorted(
            meter_key
            for meter_key, meter_data in data.meters.items()
            if meter_data.available
        ),
        "unavailable_meters": sorted(
            meter_key
            for meter_key, meter_data in data.meters.items()
            if not meter_data.available
        ),
        "last_successful_updates": {
            meter_key: _format_datetime(meter_data.last_successful_update)
            for meter_key, meter_data in data.meters.items()
        },
    }


def _format_datetime(value: datetime | None) -> str | None:
    """Return an ISO formatted datetime for diagnostics."""
    if value is None:
        return None
    return value.isoformat()
