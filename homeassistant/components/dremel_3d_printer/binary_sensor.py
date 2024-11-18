"""Support for monitoring Dremel 3D Printer binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dremel3dpy import Dremel3DPrinter

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import DremelConfigEntry
from .entity import Dremel3DPrinterEntity


@dataclass(frozen=True, kw_only=True)
class Dremel3DPrinterBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Dremel 3D Printer binary sensor."""

    value_fn: Callable[[Dremel3DPrinter], bool]


BINARY_SENSOR_TYPES: tuple[Dremel3DPrinterBinarySensorEntityDescription, ...] = (
    Dremel3DPrinterBinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda api: api.is_door_open(),
    ),
    Dremel3DPrinterBinarySensorEntityDescription(
        key="running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda api: api.is_running(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DremelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Dremel binary sensors."""
    async_add_entities(
        Dremel3DPrinterBinarySensor(config_entry.runtime_data, description)
        for description in BINARY_SENSOR_TYPES
    )


class Dremel3DPrinterBinarySensor(Dremel3DPrinterEntity, BinarySensorEntity):
    """Representation of a Dremel 3D Printer door binary sensor."""

    entity_description: Dremel3DPrinterBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if door is open."""
        return self.entity_description.value_fn(self._api)
