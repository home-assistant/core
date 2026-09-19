"""Provides diagnostics for Teslemetry."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms

from . import TeslemetryConfigEntry
from .const import DOMAIN
from .entity import TeslemetryVehicleCommandEntity, TeslemetryVehicleStreamEntity
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

SOURCE_POLLING = "polling"
SOURCE_STREAMING = "streaming"
SOURCE_COMMAND = "command"
SOURCE_ENABLED = "enabled"


@callback
def _async_vehicle_entity_sources(
    entity_entries: list[er.RegistryEntry],
    entities: dict[str, Entity],
    vehicle: TeslemetryVehicleData,
) -> dict[str, str]:
    """Map each enabled vehicle entity to its data source.

    A listener only costs credits while its coordinator is scheduled to
    refresh, which needs an update interval - set only when command signing is
    off - and polling left enabled on the config entry, so listeners are only
    reported as "polling" when both hold, mirroring the guards in
    DataUpdateCoordinator._schedule_refresh. "streaming" entities belong to the
    telemetry stream family. "command" entities only send commands and read no
    state at all, so no source can be attributed to them. Anything else enabled
    in the registry, a listener that cannot cause a refresh or an entity whose
    platform is not loaded, is reported as "enabled".
    """
    coordinator = vehicle.coordinator
    polling_ids: set[str] = set()
    if (
        coordinator.update_interval is not None
        and not coordinator.config_entry.pref_disable_polling
    ):
        polling_ids = {
            context.entity_id
            for context in coordinator.async_contexts()
            if isinstance(context, Entity)
        }
    prefix = f"{vehicle.vin}-"
    sources: dict[str, str] = {}
    for entry in entity_entries:
        if entry.disabled_by or not entry.unique_id.startswith(prefix):
            continue
        entity = entities.get(entry.entity_id)
        if entry.entity_id in polling_ids:
            sources[entry.entity_id] = SOURCE_POLLING
        elif isinstance(entity, TeslemetryVehicleStreamEntity):
            sources[entry.entity_id] = SOURCE_STREAMING
        elif isinstance(entity, TeslemetryVehicleCommandEntity):
            sources[entry.entity_id] = SOURCE_COMMAND
        else:
            sources[entry.entity_id] = SOURCE_ENABLED
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
