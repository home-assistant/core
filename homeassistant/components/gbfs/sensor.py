"""Sensors for GBFS stations."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiomobilitydatabase.feeds import Station, VehicleType

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, DOMAIN
from .coordinator import GbfsConfigEntry, GbfsCoordinator

PARALLEL_UPDATES = 0

GROUPS = (
    "classic_bikes",
    "e_bikes",
    "cargo_bikes",
    "scooters",
    "mopeds",
    "cars",
    "other_vehicles",
)

_FORM_FACTOR_GROUPS = {
    "cargo_bicycle": "cargo_bikes",
    "scooter_standing": "scooters",
    "scooter_seated": "scooters",
    # GBFS 2.2; 2.3 split it into standing and seated.
    "scooter": "scooters",
    "moped": "mopeds",
    "car": "cars",
    "other": "other_vehicles",
}


def vehicle_group(vehicle_type: VehicleType) -> str | None:
    """Return the sensor group a vehicle type counts towards."""
    if vehicle_type.form_factor == "bicycle":
        # Unknown future propulsion types are motorized; human is the only unpowered one.
        if vehicle_type.propulsion_type in ("human", None):
            return "classic_bikes"
        return "e_bikes"
    if vehicle_type.form_factor is None:
        return None
    return _FORM_FACTOR_GROUPS.get(vehicle_type.form_factor)


@dataclass(frozen=True, kw_only=True)
class GbfsSensorEntityDescription(SensorEntityDescription):
    """Describes a GBFS station sensor."""

    value_fn: Callable[[Station], int | None]


VEHICLES_AVAILABLE = GbfsSensorEntityDescription(
    key="vehicles_available",
    translation_key="vehicles_available",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda station: station.bikes_available,
)

DOCKS_AVAILABLE = GbfsSensorEntityDescription(
    key="docks_available",
    translation_key="docks_available",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda station: station.docks_available,
)


def _group_description(
    group: str, type_ids: frozenset[str]
) -> GbfsSensorEntityDescription:
    """Describe the sensor counting one group's vehicle types at a station."""

    def value(station: Station) -> int | None:
        if station.vehicle_types_available is None:
            return None
        return sum(
            count
            for type_id, count in station.vehicle_types_available.items()
            if type_id in type_ids
        )

    return GbfsSensorEntityDescription(
        key=group,
        translation_key=group,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GbfsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for each station subentry."""
    coordinator = entry.runtime_data
    type_ids: dict[str, set[str]] = {}
    for vehicle_type in coordinator.vehicle_types:
        if (group := vehicle_group(vehicle_type)) is not None:
            type_ids.setdefault(group, set()).add(vehicle_type.id)
    group_descriptions = [
        _group_description(group, frozenset(type_ids[group]))
        for group in GROUPS
        if group in type_ids
    ]
    for subentry_id, subentry in entry.subentries.items():
        station = coordinator.data.get(subentry.data[CONF_STATION_ID])
        descriptions = [VEHICLES_AVAILABLE]
        if station is not None and station.docks_available is not None:
            descriptions.append(DOCKS_AVAILABLE)
        descriptions.extend(group_descriptions)
        async_add_entities(
            (
                GbfsStationSensor(coordinator, subentry, description)
                for description in descriptions
            ),
            config_subentry_id=subentry_id,
        )


class GbfsStationSensor(CoordinatorEntity[GbfsCoordinator], SensorEntity):
    """A count at one GBFS station."""

    _attr_has_entity_name = True
    entity_description: GbfsSensorEntityDescription

    def __init__(
        self,
        coordinator: GbfsCoordinator,
        subentry: ConfigSubentry,
        description: GbfsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id: str = subentry.data[CONF_STATION_ID]
        system = coordinator.system
        self._attr_unique_id = (
            f"{system.system_id}_{self._station_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{system.system_id}_{self._station_id}")},
            name=subentry.title,
            manufacturer=system.operator or system.name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the station is in the feed and installed."""
        station = self.coordinator.data.get(self._station_id)
        return (
            super().available
            and station is not None
            and station.is_installed is not False
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the count."""
        return self.entity_description.value_fn(self.coordinator.data[self._station_id])
