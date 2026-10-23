"""Provides diagnostics for Teslemetry."""

from typing import Any

from tesla_fleet_api.router import VehicleRouter

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
    "backseat_token",
    "id_s",
    "drive_state_active_route_latitude",
    "drive_state_active_route_longitude",
    "drive_state_latitude",
    "drive_state_longitude",
    "drive_state_native_latitude",
    "drive_state_native_longitude",
    "charge_schedule_data_charge_schedule_window_latitude",
    "charge_schedule_data_charge_schedule_window_longitude",
    "preconditioning_schedule_data_preconditioning_schedule_window_latitude",
    "preconditioning_schedule_data_preconditioning_schedule_window_longitude",
    # Schedule lists are not flattened, so their entries keep plain keys
    "latitude",
    "longitude",
    # Bluetooth address of a paired vehicle
    "address",
]

ENERGY_LIVE_REDACT = ["vin", "din"]
ENERGY_INFO_REDACT = ["id", "installation_date", "din", "serial_number"]

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

    Listeners only count as polling when the coordinator will actually refresh,
    mirroring the guards in DataUpdateCoordinator._schedule_refresh.
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
    vehicles = []
    for x in entry.runtime_data.vehicles:
        # A paired vehicle stays on the cloud API when its Bluetooth key fails to load.
        router = x.api if isinstance(x.api, VehicleRouter) else None
        vehicles.append(
            {
                "data": async_redact_data(x.coordinator.data, VEHICLE_REDACT),
                "entities": _async_vehicle_entity_sources(entity_entries, entities, x),
                "stream": {
                    "config": x.stream_vehicle.config,
                },
                "bluetooth": async_redact_data(
                    {
                        "paired": x.ble_address is not None,
                        "address": x.ble_address,
                        "backend": "router" if router else "cloud",
                        "in_range": await router.is_healthy() if router else None,
                    },
                    VEHICLE_REDACT,
                ),
            }
        )
    energysites = [
        {
            # Wall connectors are keyed by DIN, which embeds the serial number
            "live": async_redact_data(
                {
                    **x.live_coordinator.data,
                    "wall_connectors": list(
                        x.live_coordinator.data["wall_connectors"].values()
                    ),
                },
                ENERGY_LIVE_REDACT,
            )
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
