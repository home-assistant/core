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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FAADataUpdateCoordinator
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class FaaDelaysBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Mixin for required keys."""

    is_on_fn: Callable[[Airport], bool | None]
    extra_state_attributes_fn: Callable[[Airport], Mapping[str, Any]]


FAA_BINARY_SENSORS: tuple[FaaDelaysBinarySensorEntityDescription, ...] = (
    FaaDelaysBinarySensorEntityDescription(
        key="GROUND_DELAY",
        translation_key="ground_delay",
        is_on_fn=lambda airport: airport.ground_delay.status,
        extra_state_attributes_fn=lambda airport: {
            "average": airport.ground_delay.average,
            "reason": airport.ground_delay.reason,
        },
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="GROUND_STOP",
        translation_key="ground_stop",
        is_on_fn=lambda airport: airport.ground_stop.status,
        extra_state_attributes_fn=lambda airport: {
            "endtime": airport.ground_stop.endtime,
            "reason": airport.ground_stop.reason,
        },
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="DEPART_DELAY",
        translation_key="depart_delay",
        is_on_fn=lambda airport: airport.depart_delay.status,
        extra_state_attributes_fn=lambda airport: {
            "minimum": airport.depart_delay.minimum,
            "maximum": airport.depart_delay.maximum,
            "trend": airport.depart_delay.trend,
            "reason": airport.depart_delay.reason,
        },
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="ARRIVE_DELAY",
        translation_key="arrive_delay",
        is_on_fn=lambda airport: airport.arrive_delay.status,
        extra_state_attributes_fn=lambda airport: {
            "minimum": airport.arrive_delay.minimum,
            "maximum": airport.arrive_delay.maximum,
            "trend": airport.arrive_delay.trend,
            "reason": airport.arrive_delay.reason,
        },
    ),
    FaaDelaysBinarySensorEntityDescription(
        key="CLOSURE",
        translation_key="closure",
        is_on_fn=lambda airport: airport.closure.status,
        extra_state_attributes_fn=lambda airport: {
            "begin": airport.closure.start,
            "end": airport.closure.end,
        },
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

    _attr_has_entity_name = True

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
        _id = coordinator.data.code
        self._attr_unique_id = f"{_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, _id)},
            name=_id,
            manufacturer="Federal Aviation Administration",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the status of the sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return attributes for sensor."""
        return self.entity_description.extra_state_attributes_fn(self.coordinator.data)
