"""Diagnostics support for Nederlandse Spoorwegen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import NSConfigEntry

TO_REDACT = [
    CONF_API_KEY,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NSConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators_data = {}

    # Collect data from all coordinators
    for subentry_id, coordinator in entry.runtime_data.items():
        coordinators_data[subentry_id] = {
            "coordinator_info": {
                "name": coordinator.name,
                "departure": coordinator.departure,
                "destination": coordinator.destination,
                "via": coordinator.via,
                "departure_time": coordinator.departure_time,
            },
            "route_data": {
                "trips_count": len(coordinator.data.trips) if coordinator.data else 0,
                "has_first_trip": coordinator.data.first_trip is not None
                if coordinator.data
                else False,
                "has_next_trip": coordinator.data.next_trip is not None
                if coordinator.data
                else False,
            }
            if coordinator.data
            else None,
        }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "coordinators": coordinators_data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: NSConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a route."""
    # Find the coordinator for this device
    coordinator = None
    subentry_id = None

    # Each device has an identifier (DOMAIN, subentry_id)
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            subentry_id = identifier[1]
            coordinator = entry.runtime_data.get(subentry_id)
            break

    # Collect detailed diagnostics for this specific route
    device_data = {
        "device_info": {
            "subentry_id": subentry_id,
            "device_name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
        },
        "coordinator_info": {
            "name": coordinator.name,
            "departure": coordinator.departure,
            "destination": coordinator.destination,
            "via": coordinator.via,
            "departure_time": coordinator.departure_time,
        }
        if coordinator
        else None,
    }

    # Add detailed trip data if available
    if coordinator and coordinator.data:
        device_data["trip_details"] = {
            "trips_count": len(coordinator.data.trips),
            "has_first_trip": coordinator.data.first_trip is not None,
            "has_next_trip": coordinator.data.next_trip is not None,
        }

        # Add first trip details if available
        if coordinator.data.first_trip:
            first_trip = coordinator.data.first_trip
            device_data["first_trip"] = {
                "departure_time_planned": str(first_trip.departure_time_planned)
                if first_trip.departure_time_planned
                else None,
                "departure_time_actual": str(first_trip.departure_time_actual)
                if first_trip.departure_time_actual
                else None,
                "arrival_time_planned": str(first_trip.arrival_time_planned)
                if first_trip.arrival_time_planned
                else None,
                "arrival_time_actual": str(first_trip.arrival_time_actual)
                if first_trip.arrival_time_actual
                else None,
                "departure_platform_planned": first_trip.departure_platform_planned,
                "departure_platform_actual": first_trip.departure_platform_actual,
                "arrival_platform_planned": first_trip.arrival_platform_planned,
                "arrival_platform_actual": first_trip.arrival_platform_actual,
                "status": str(first_trip.status) if first_trip.status else None,
                "nr_transfers": first_trip.nr_transfers,
                "going": first_trip.going,
            }

    return device_data
