"""Support for Big Ass Fans binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from aiobafi6 import Device

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BAFConfigEntry
from .entity import BAFDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class BAFBinarySensorDescription(
    BinarySensorEntityDescription,
):
    """Class describing BAF binary sensor entities."""

    value_fn: Callable[[Device], bool | None]


OCCUPANCY_SENSORS = (
    BAFBinarySensorDescription(
        key="occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        value_fn=lambda device: cast(bool | None, device.fan_occupancy_detected),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF binary sensors."""
    device = entry.runtime_data
    if device.has_occupancy:
        async_add_entities(
            BAFBinarySensor(device, description) for description in OCCUPANCY_SENSORS
        )


class BAFBinarySensor(BAFDescriptionEntity, BinarySensorEntity):
    """BAF binary sensor."""

    entity_description: BAFBinarySensorDescription

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self.entity_description.value_fn(self._device)
