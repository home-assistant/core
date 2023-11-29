"""Platform for FAA Delays sensor component."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from faadelays import Airport

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FAADataUpdateCoordinator
from .const import DOMAIN


@dataclass(kw_only=True)
class FaaDelaysBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Mixin for required keys."""

    is_on_fn: Callable[[Airport], bool | None]


FAA_BINARY_SENSORS: tuple[FaaDelaysBinarySensorEntityDescription, ...] = (
    FaaDelaysBinarySensorEntityDescription(
        key="GROUND_DELAY",
        name="Ground Delay",
        icon="mdi:airport",
        is_on_fn=lambda airport: airport.ground_delay.status,
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="GROUND_STOP",
        name="Ground Stop",
        icon="mdi:airport",
        is_on_fn=lambda airport: airport.ground_stop.status,
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="DEPART_DELAY",
        name="Departure Delay",
        icon="mdi:airplane-takeoff",
        is_on_fn=lambda airport: airport.depart_delay.status,
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="ARRIVE_DELAY",
        name="Arrival Delay",
        icon="mdi:airplane-landing",
        is_on_fn=lambda airport: airport.arrive_delay.status,
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="CLOSURE",
        name="Closure",
        icon="mdi:airplane:off",
        is_on_fn=lambda airport: airport.closure.status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a FAA sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        FAABinarySensor(coordinator, entry.entry_id, description)
        for description in FAA_BINARY_SENSORS
    ]

    async_add_entities(entities)


class FAABinarySensor(CoordinatorEntity[FAADataUpdateCoordinator], BinarySensorEntity):
    """Define a binary sensor for FAA Delays."""

    entity_description: FaaDelaysBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FAADataUpdateCoordinator,
        entry_id: str,
        description: FaaDelaysBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self.coordinator = coordinator
        self._entry_id = entry_id
        self._attrs: dict[str, Any] = {}
        _id = coordinator.data.code
        self._attr_name = f"{_id} {description.name}"
        self._attr_unique_id = f"{_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the status of the sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return attributes for sensor."""
        sensor_type = self.entity_description.key
        if sensor_type == "GROUND_DELAY":
            self._attrs["average"] = self.coordinator.data.ground_delay.average
            self._attrs["reason"] = self.coordinator.data.ground_delay.reason
        elif sensor_type == "GROUND_STOP":
            self._attrs["endtime"] = self.coordinator.data.ground_stop.endtime
            self._attrs["reason"] = self.coordinator.data.ground_stop.reason
        elif sensor_type == "DEPART_DELAY":
            self._attrs["minimum"] = self.coordinator.data.depart_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.depart_delay.maximum
            self._attrs["trend"] = self.coordinator.data.depart_delay.trend
            self._attrs["reason"] = self.coordinator.data.depart_delay.reason
        elif sensor_type == "ARRIVE_DELAY":
            self._attrs["minimum"] = self.coordinator.data.arrive_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.arrive_delay.maximum
            self._attrs["trend"] = self.coordinator.data.arrive_delay.trend
            self._attrs["reason"] = self.coordinator.data.arrive_delay.reason
        elif sensor_type == "CLOSURE":
            self._attrs["begin"] = self.coordinator.data.closure.start
            self._attrs["end"] = self.coordinator.data.closure.end
        return self._attrs
