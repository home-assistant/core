"""Diagnostics support for Nederlandse Spoorwegen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import NSConfigEntry
from .const import CONF_FROM, CONF_NAME, CONF_TO, CONF_VIA


def _sanitize_route_data(route_data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize route data for diagnostics."""
    route_info = route_data.get("route", {})
    safe_route_data = {
        "route": {
            CONF_NAME: "redacted",  # Always redact route names for privacy
            CONF_FROM: route_info.get(CONF_FROM),  # Station codes are public data
            CONF_TO: route_info.get(CONF_TO),  # Station codes are public data
            CONF_VIA: route_info.get(CONF_VIA),  # Station codes are public data
        },
        "has_first_trip": "first_trip" in route_data,
        "has_next_trip": "next_trip" in route_data,
        "data_keys": list(route_data.keys()) if isinstance(route_data, dict) else [],
    }

    # Add trip information structure (without actual data)
    if route_data.get("first_trip"):
        trip_data = route_data["first_trip"]
        if isinstance(trip_data, dict):
            safe_route_data["first_trip_structure"] = {
                "available_fields": list(trip_data.keys()),
                "has_departure_time": "departure_time_planned" in trip_data
                or "departure_time_actual" in trip_data,
                "has_arrival_time": "arrival_time_planned" in trip_data
                or "arrival_time_actual" in trip_data,
                "has_platform_info": "departure_platform_planned" in trip_data
                or "arrival_platform_planned" in trip_data,
                "has_status": "status" in trip_data,
                "has_transfers": "nr_transfers" in trip_data,
            }

    return safe_route_data


# Sensitive data fields to redact
TO_REDACT = {
    CONF_API_KEY,
    "unique_id",
    "entry_id",
}

# Route-specific fields to redact
ROUTE_TO_REDACT = {
    "api_key",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NSConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator

    # Base diagnostics data
    entry_dict = entry.as_dict()
    diagnostics_data: dict[str, Any] = {
        "entry": async_redact_data(entry_dict, TO_REDACT)
        if isinstance(entry_dict, dict)
        else {},
        "coordinator_data": None,
        "coordinator_status": {
            "last_update_success": coordinator.last_update_success
            if coordinator
            else None,
            "last_exception": str(coordinator.last_exception)
            if coordinator and coordinator.last_exception
            else None,
            "update_count": getattr(coordinator, "update_count", None)
            if coordinator
            else None,
        },
        "runtime_data": {
            "stations_count": len(runtime_data.stations)
            if runtime_data.stations
            else 0,
            "stations_updated": runtime_data.stations_updated,
        },
        "subentries": {},
    }

    # Coordinator data
    if coordinator and coordinator.data:
        coordinator_data: dict[str, Any] = {
            "routes": {},
            "stations": {},
            "last_updated": coordinator.data.get("last_updated"),
        }

        # Route information
        if coordinator.data.get("routes"):
            route_counter = 1
            for route_data in coordinator.data["routes"].values():
                # Sanitize route data
                if isinstance(route_data, dict):
                    safe_route_data = _sanitize_route_data(route_data)
                    coordinator_data["routes"][f"route_{route_counter}"] = (
                        safe_route_data
                    )
                    route_counter += 1

        # Station data
        if coordinator.data.get("stations"):
            stations = coordinator.data["stations"]
            coordinator_data["stations"] = {
                "count": len(stations),
                "sample_structure": {
                    "available_fields": list(stations[0].__dict__.keys())
                    if stations and hasattr(stations[0], "__dict__")
                    else [],
                }
                if stations
                else {},
            }

        diagnostics_data["coordinator_data"] = coordinator_data

    # Subentry information
    subentry_counter = 1
    for subentry in entry.subentries.values():
        subentry_dict = subentry.as_dict()
        redacted_subentry = (
            async_redact_data(subentry_dict, TO_REDACT)
            if isinstance(subentry_dict, dict)
            else {}
        )

        subentry_data: dict[str, Any] = {
            "subentry_info": redacted_subentry,
            "route_config": {
                CONF_NAME: "redacted",  # Always redact route names for privacy
                CONF_FROM: subentry.data.get(
                    CONF_FROM
                ),  # Station codes are public data
                CONF_TO: subentry.data.get(CONF_TO),  # Station codes are public data
                CONF_VIA: subentry.data.get(CONF_VIA),  # Station codes are public data
                "data_keys": list(subentry.data.keys()),
            },
        }
        diagnostics_data["subentries"][f"subentry_{subentry_counter}"] = subentry_data
        subentry_counter += 1

    # Integration health
    diagnostics_data["integration_health"] = {
        "coordinator_available": coordinator is not None,
        "coordinator_has_data": coordinator is not None
        and coordinator.data is not None,
        "routes_configured": len(entry.subentries),
        "api_connection_status": "healthy"
        if coordinator and coordinator.last_update_success
        else "issues",
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: NSConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    # For NS integration, devices represent routes
    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator

    # Find the route data for this device
    device_route_data = None
    device_subentry = None

    # Look for the device in subentries
    for subentry_id, subentry in entry.subentries.items():
        # Check if device identifiers match
        if device.identifiers and any(
            identifier[1] == subentry_id
            for identifier in device.identifiers
            if identifier[0] == entry.domain
        ):
            device_subentry = subentry
            # Find corresponding route data
            if coordinator and coordinator.data and "routes" in coordinator.data:
                route_key = f"{subentry.data.get(CONF_NAME, '')}_{subentry.data.get(CONF_FROM, '')}_{subentry.data.get(CONF_TO, '')}"
                device_route_data = coordinator.data["routes"].get(route_key)
            break

    diagnostics: dict[str, Any] = {
        "device_info": {
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "sw_version": device.sw_version,
            "identifiers": [
                f"{identifier[0]}:{identifier[1]}" for identifier in device.identifiers
            ]
            if device.identifiers
            else [],
        },
        "route_config": {},
        "route_data_status": {
            "has_data": device_route_data is not None,
            "data_structure": {},
        },
    }

    # Add route configuration if available
    if device_subentry:
        diagnostics["route_config"] = {
            CONF_NAME: "redacted",  # Always redact route names for privacy
            CONF_FROM: device_subentry.data.get(
                CONF_FROM
            ),  # Station codes are public data
            CONF_TO: device_subentry.data.get(CONF_TO),  # Station codes are public data
            CONF_VIA: device_subentry.data.get(
                CONF_VIA
            ),  # Station codes are public data
            "config_keys": list(device_subentry.data.keys()),
        }

    # Add route data structure (without sensitive content)
    if device_route_data and isinstance(device_route_data, dict):
        route_data_status = diagnostics["route_data_status"]
        if isinstance(route_data_status, dict):
            route_data_status["data_structure"] = {
                "available_keys": list(device_route_data.keys()),
                "has_first_trip": "first_trip" in device_route_data,
                "has_next_trip": "next_trip" in device_route_data,
            }

            # Add trip data structure
            if device_route_data.get("first_trip"):
                trip = device_route_data["first_trip"]
                if isinstance(trip, dict):
                    route_data_status["first_trip_structure"] = {
                        "available_fields": list(trip.keys()),
                        "timing_data": {
                            "has_planned_departure": "departure_time_planned" in trip,
                            "has_actual_departure": "departure_time_actual" in trip,
                            "has_planned_arrival": "arrival_time_planned" in trip,
                            "has_actual_arrival": "arrival_time_actual" in trip,
                        },
                        "platform_data": {
                            "has_planned_departure_platform": "departure_platform_planned"
                            in trip,
                            "has_actual_departure_platform": "departure_platform_actual"
                            in trip,
                            "has_planned_arrival_platform": "arrival_platform_planned"
                            in trip,
                            "has_actual_arrival_platform": "arrival_platform_actual"
                            in trip,
                        },
                        "has_status": "status" in trip,
                        "has_transfers": "nr_transfers" in trip,
                    }

    return diagnostics
