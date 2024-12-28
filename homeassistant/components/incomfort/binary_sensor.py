"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from incomfortclient import Heater as InComfortHeater

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InComfortConfigEntry
from .coordinator import InComfortDataCoordinator
from .entity import IncomfortBoilerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IncomfortBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Incomfort binary sensor entity."""

    value_key: str
    extra_state_attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSOR_TYPES: tuple[IncomfortBinarySensorEntityDescription, ...] = (
    IncomfortBinarySensorEntityDescription(
        key="failed",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_key="is_failed",
        extra_state_attributes_fn=lambda status: {
            "fault_code": status["fault_code"] or "none",
        },
    ),
    IncomfortBinarySensorEntityDescription(
        key="is_pumping",
        translation_key="is_pumping",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_key="is_pumping",
    ),
    IncomfortBinarySensorEntityDescription(
        key="is_burning",
        translation_key="is_burning",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_key="is_burning",
    ),
    IncomfortBinarySensorEntityDescription(
        key="is_tapping",
        translation_key="is_tapping",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_key="is_tapping",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an InComfort/InTouch binary_sensor entity."""
    incomfort_coordinator = entry.runtime_data
    heaters = incomfort_coordinator.data.heaters
    async_add_entities(
        IncomfortBinarySensor(incomfort_coordinator, h, description)
        for h in heaters
        for description in SENSOR_TYPES
    )


class IncomfortBinarySensor(IncomfortBoilerEntity, BinarySensorEntity):
    """Representation of an InComfort binary sensor."""

    entity_description: IncomfortBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: InComfortDataCoordinator,
        heater: InComfortHeater,
        description: IncomfortBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, heater)
        self.entity_description = description
        self._attr_unique_id = f"{heater.serial_no}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._heater.status[self.entity_description.value_key]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if (attributes_fn := self.entity_description.extra_state_attributes_fn) is None:
            return None
        return attributes_fn(self._heater.status)
