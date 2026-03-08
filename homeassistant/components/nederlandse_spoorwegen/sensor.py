"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ns_api import Trip

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor import get_delay
from .const import DOMAIN, INTEGRATION_TITLE, ROUTE_MODEL
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator


def get_departure_time(trip: Trip | None) -> datetime | None:
    """Get next departure time from trip data."""
    return trip.departure_time_actual or trip.departure_time_planned if trip else None


def _get_time_str(time: datetime | None) -> str | None:
    """Get time as string."""
    return time.strftime("%H:%M") if time else None


def _get_route(trip: Trip | None) -> list[str]:
    """Get the route as a list of station names from trip data."""
    if not trip or not (trip_parts := trip.trip_parts):
        return []
    route = []
    if departure := trip.departure:
        route.append(departure)
    route.extend(part.destination for part in trip_parts)
    return route


TRIP_STATUS = {
    "NORMAL": "normal",
    "CANCELLED": "cancelled",
}


PARALLEL_UPDATES = 0  # since we use coordinator pattern


@dataclass(frozen=True, kw_only=True)
class NSSensorEntityDescription(SensorEntityDescription):
    """Describes Nederlandse Spoorwegen sensor entity."""

    is_next: bool = False
    value_fn: Callable[[Trip], datetime | str | int | None]
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC


# Entity descriptions for all the different sensors we create per route
SENSOR_DESCRIPTIONS: tuple[NSSensorEntityDescription, ...] = (
    NSSensorEntityDescription(
        key="actual_departure",
        translation_key="departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=None,
        value_fn=get_departure_time,
    ),
    NSSensorEntityDescription(
        key="next_departure",
        translation_key="next_departure_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        is_next=True,
        value_fn=get_departure_time,
        entity_registry_enabled_default=False,
    ),
    # Platform information
    NSSensorEntityDescription(
        key="departure_platform_planned",
        translation_key="departure_platform_planned",
        value_fn=lambda trip: getattr(trip, "departure_platform_planned", None),
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="departure_platform_actual",
        translation_key="departure_platform_actual",
        value_fn=lambda trip: trip.departure_platform_actual,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="arrival_platform_planned",
        translation_key="arrival_platform_planned",
        value_fn=lambda trip: trip.arrival_platform_planned,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="arrival_platform_actual",
        translation_key="arrival_platform_actual",
        value_fn=lambda trip: trip.arrival_platform_actual,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="departure_time_planned",
        translation_key="departure_time_planned",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda trip: trip.departure_time_planned,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="departure_time_actual",
        translation_key="departure_time_actual",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda trip: trip.departure_time_actual,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="arrival_time_planned",
        translation_key="arrival_time_planned",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda trip: trip.arrival_time_planned,
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="arrival_time_actual",
        translation_key="arrival_time_actual",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda trip: trip.arrival_time_actual,
        entity_registry_enabled_default=False,
    ),
    # Trip information
    NSSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(TRIP_STATUS.values()),
        value_fn=lambda trip: TRIP_STATUS.get(trip.status),
        entity_registry_enabled_default=False,
    ),
    NSSensorEntityDescription(
        key="transfers",
        translation_key="transfers",
        value_fn=lambda trip: trip.nr_transfers if trip else 0,
        entity_registry_enabled_default=False,
    ),
    # Route info sensors
    NSSensorEntityDescription(
        key="route",
        translation_key="route",
        value_fn=lambda trip: ", ".join(_get_route(trip)),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the departure sensor from a config entry."""

    coordinators = config_entry.runtime_data

    for subentry_id, coordinator in coordinators.items():
        async_add_entities(
            [
                NSSensor(coordinator, subentry_id, description)
                for description in SENSOR_DESCRIPTIONS
            ],
            config_subentry_id=subentry_id,
        )


class NSSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Generic NS sensor based on entity description."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"
    entity_description: NSSensorEntityDescription

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        subentry_id: str,
        description: NSSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_entity_category = description.entity_category
        self._subentry_id = subentry_id

        self._attr_unique_id = f"{subentry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=coordinator.name,
            manufacturer=INTEGRATION_TITLE,
            model=ROUTE_MODEL,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value of the sensor."""
        data = (
            self.coordinator.data.first_trip
            if not self.entity_description.is_next
            else self.coordinator.data.next_trip
        )
        if data is None:
            return None

        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.key != "actual_departure":
            return None

        first_trip = self.coordinator.data.first_trip
        next_trip = self.coordinator.data.next_trip

        if not first_trip:
            return None

        status = first_trip.status

        # Static attributes
        return {
            "going": first_trip.going,
            "departure_time_planned": _get_time_str(first_trip.departure_time_planned),
            "departure_time_actual": _get_time_str(first_trip.departure_time_actual),
            "departure_delay": get_delay(
                first_trip.departure_time_planned,
                first_trip.departure_time_actual,
            ),
            "departure_platform_planned": first_trip.departure_platform_planned,
            "departure_platform_actual": first_trip.departure_platform_actual,
            "arrival_time_planned": _get_time_str(first_trip.arrival_time_planned),
            "arrival_time_actual": _get_time_str(first_trip.arrival_time_actual),
            "arrival_delay": get_delay(
                first_trip.arrival_time_planned,
                first_trip.arrival_time_actual,
            ),
            "arrival_platform_planned": first_trip.arrival_platform_planned,
            "arrival_platform_actual": first_trip.arrival_platform_actual,
            "next": _get_time_str(get_departure_time(next_trip)),
            "status": status.lower() if status else None,
            "transfers": first_trip.nr_transfers,
            "route": _get_route(first_trip),
            "remarks": None,
        }
