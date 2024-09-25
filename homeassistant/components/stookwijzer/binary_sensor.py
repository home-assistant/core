"""Support for Stookwijzer Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import StookwijzerCoordinator
from .entity import StookwijzerEntity


@dataclass(kw_only=True, frozen=True)
class StookwijzerBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Stookwijzer binary sensor entities."""

    value_fn: Callable[[StookwijzerCoordinator], bool | None]


STOOKWIJZER_BINARY_SENSORS = [
    StookwijzerBinarySensorDescription(
        key="stookalert",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda StookwijzerCoordinator: StookwijzerCoordinator.client.alert,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer binary sensor from a config entry."""

    async_add_entities(
        StookwijzerBinarySensor(description, entry)
        for description in STOOKWIJZER_BINARY_SENSORS
    )


class StookwijzerBinarySensor(StookwijzerEntity, BinarySensorEntity):
    """Defines a Stookwijzer binary sensor."""

    entity_description: StookwijzerBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self._coordinator)
