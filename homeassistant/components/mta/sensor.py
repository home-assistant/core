"""Sensor platform for MTA New York City Transit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, CONF_ROUTE, CONF_STOP_NAME, DOMAIN, SUBENTRY_TYPE_BUS
from .coordinator import MTAArrival, MTAConfigEntry, MTADataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MTASensorEntityDescription(SensorEntityDescription):
    """Describes an MTA sensor entity."""

    arrival_index: int
    value_fn: Callable[[MTAArrival], datetime | str]


SENSOR_DESCRIPTIONS: tuple[MTASensorEntityDescription, ...] = (
    MTASensorEntityDescription(
        key="next_arrival",
        translation_key="next_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        arrival_index=0,
        value_fn=lambda arrival: arrival.arrival_time,
    ),
    MTASensorEntityDescription(
        key="next_arrival_route",
        translation_key="next_arrival_route",
        arrival_index=0,
        value_fn=lambda arrival: arrival.route_id,
    ),
    MTASensorEntityDescription(
        key="next_arrival_destination",
        translation_key="next_arrival_destination",
        arrival_index=0,
        value_fn=lambda arrival: arrival.destination,
    ),
    MTASensorEntityDescription(
        key="second_arrival",
        translation_key="second_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        arrival_index=1,
        value_fn=lambda arrival: arrival.arrival_time,
    ),
    MTASensorEntityDescription(
        key="second_arrival_route",
        translation_key="second_arrival_route",
        arrival_index=1,
        value_fn=lambda arrival: arrival.route_id,
    ),
    MTASensorEntityDescription(
        key="second_arrival_destination",
        translation_key="second_arrival_destination",
        arrival_index=1,
        value_fn=lambda arrival: arrival.destination,
    ),
    MTASensorEntityDescription(
        key="third_arrival",
        translation_key="third_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        arrival_index=2,
        value_fn=lambda arrival: arrival.arrival_time,
    ),
    MTASensorEntityDescription(
        key="third_arrival_route",
        translation_key="third_arrival_route",
        arrival_index=2,
        value_fn=lambda arrival: arrival.route_id,
    ),
    MTASensorEntityDescription(
        key="third_arrival_destination",
        translation_key="third_arrival_destination",
        arrival_index=2,
        value_fn=lambda arrival: arrival.destination,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MTAConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MTA sensor based on a config entry."""
    for subentry_id, coordinator in entry.runtime_data.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            (
                MTASensor(coordinator, subentry, description)
                for description in SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry_id,
        )


class MTASensor(CoordinatorEntity[MTADataUpdateCoordinator], SensorEntity):
    """Sensor for MTA transit arrivals."""

    _attr_has_entity_name = True
    entity_description: MTASensorEntityDescription

    def __init__(
        self,
        coordinator: MTADataUpdateCoordinator,
        subentry: ConfigSubentry,
        description: MTASensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        is_bus = subentry.subentry_type == SUBENTRY_TYPE_BUS
        if is_bus:
            route = subentry.data[CONF_ROUTE]
            model = "Bus"
        else:
            route = subentry.data[CONF_LINE]
            model = "Subway"

        stop_name = subentry.data.get(CONF_STOP_NAME, subentry.subentry_id)

        unique_id = subentry.unique_id or subentry.subentry_id
        self._attr_unique_id = f"{unique_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=f"{route} - {stop_name}",
            manufacturer="MTA",
            model=model,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | str | None:
        """Return the state of the sensor."""
        arrivals = self.coordinator.data.arrivals
        if len(arrivals) <= self.entity_description.arrival_index:
            return None

        return self.entity_description.value_fn(
            arrivals[self.entity_description.arrival_index]
        )
