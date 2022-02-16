"""Support for Aseko Pool Live binary sensors."""
from __future__ import annotations

from typing import cast

from aioaseko import Unit

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AsekoDataUpdateCoordinator
from .const import DOMAIN
from .entity import AsekoEntity

UNIT_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="water_flow",
        name="Water Flow",
        icon="mdi:waves-arrow-right",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="has_alarm", name="Alarm", device_class=BinarySensorDeviceClass.SAFETY
    ),
    BinarySensorEntityDescription(
        key="has_error", name="Error", device_class=BinarySensorDeviceClass.PROBLEM
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aseko Pool Live binary sensors."""
    data: list[tuple[Unit, AsekoDataUpdateCoordinator]] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[BinarySensorEntity] = []
    for unit, coordinator in data:
        for description in UNIT_BINARY_SENSORS:
            entities.append(AsekoUnitBinarySensorEntity(unit, coordinator, description))
    async_add_entities(entities)


class AsekoUnitBinarySensorEntity(AsekoEntity, BinarySensorEntity):
    """Representation of a unit water flow binary sensor entity."""

    def __init__(
        self,
        unit: Unit,
        coordinator: AsekoDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the unit binary sensor."""
        super().__init__(unit, coordinator)
        self.entity_description = entity_description
        self._attr_name = f"{self._device_name} {self.entity_description.name}"
        self._attr_unique_id = (
            f"{self._unit.serial_number}_{self.entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return cast(bool, getattr(self._unit, self.entity_description.key))
