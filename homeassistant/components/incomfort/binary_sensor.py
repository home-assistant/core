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


@dataclass(frozen=True, kw_only=True)
class IncomfortBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Incomfort binary sensor entity."""

    value_key: str
    extra_state_attributes_fn: Callable[[dict[str, Any]], dict[str, Any]]


SENSOR_TYPES: tuple[IncomfortBinarySensorEntityDescription, ...] = (
    IncomfortBinarySensorEntityDescription(
        key="failed",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_key="is_failed",
        extra_state_attributes_fn=lambda status: {"fault_code": status["fault_code"]},
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return self.entity_description.extra_state_attributes_fn(self._heater.status)
