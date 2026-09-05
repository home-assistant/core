"""Provides diagnostics for Teslemetry."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms

from . import TeslemetryConfigEntry
from .const import DOMAIN
from .entity import TeslemetryVehicleStreamEntity
from .models import TeslemetryVehicleData

VEHICLE_REDACT = [
    "id",
    "user_id",
    "vehicle_id",
    "vin",
    "tokens",
    "id_s",
    "drive_state_active_route_latitude",
    "drive_state_active_route_longitude",
    "drive_state_latitude",
    "drive_state_longitude",
    "drive_state_native_latitude",
    "drive_state_native_longitude",
]

ENERGY_LIVE_REDACT = ["vin"]
ENERGY_INFO_REDACT = ["installation_date"]


def _async_vehicle_entity_sources(
    entity_entries: list[er.RegistryEntry],
    entities: dict[str, Entity],
    vehicle: TeslemetryVehicleData,
) -> dict[str, str]:
    """Map each enabled vehicle entity to its data source.

    "polling" entities are the vehicle coordinator's listeners, which is what
    keeps it polling; "streaming" entities belong to the telemetry stream
    family and never keep the coordinator polling. An entity enabled in the
    registry but currently neither (for example when its platform is not
    loaded) is reported as "enabled" rather than attributed to either source.
    """
    polling_ids = {
        context.entity_id
        for context in vehicle.coordinator.async_contexts()
        if isinstance(context, Entity)
    }
    prefix = f"{vehicle.vin}-"
    sources: dict[str, str] = {}
    for entry in entity_entries:
        if entry.disabled_by or not entry.unique_id.startswith(prefix):
            continue
        if entry.entity_id in polling_ids:
            sources[entry.entity_id] = "polling"
        elif isinstance(entities.get(entry.entity_id), TeslemetryVehicleStreamEntity):
            sources[entry.entity_id] = "streaming"
        else:
            sources[entry.entity_id] = "enabled"
    return dict(sorted(sources.items()))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TeslemetryConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entity_entries = er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    )
    entities = {
        entity.entity_id: entity
        for platform in async_get_platforms(hass, DOMAIN)
        if platform.config_entry is not None
        and platform.config_entry.entry_id == entry.entry_id
        for entity in platform.entities.values()
    }
    vehicles = [
        {
            "data": async_redact_data(x.coordinator.data, VEHICLE_REDACT),
            "entities": _async_vehicle_entity_sources(entity_entries, entities, x),
            "stream": {
                "config": x.stream_vehicle.config,
            },
        }
        for x in entry.runtime_data.vehicles
    ]
    energysites = [
        {
            "live": async_redact_data(x.live_coordinator.data, ENERGY_LIVE_REDACT)
            if x.live_coordinator
            else None,
            "info": async_redact_data(x.info_coordinator.data, ENERGY_INFO_REDACT),
            "history": x.history_coordinator.data if x.history_coordinator else None,
        }
        for x in entry.runtime_data.energysites
    ]

    # Return only the relevant children
    return {
        "vehicles": vehicles,
        "energysites": energysites,
        "scopes": entry.runtime_data.scopes,
    }
