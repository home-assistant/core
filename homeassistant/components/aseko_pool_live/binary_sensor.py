"""Support for Aseko Pool Live binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioaseko import Unit

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator
from .entity import AsekoEntity


@dataclass(frozen=True, kw_only=True)
class AsekoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Aseko binary sensor entity."""

    value_fn: Callable[[Unit], bool]


UNIT_BINARY_SENSORS: tuple[AsekoBinarySensorEntityDescription, ...] = (
    AsekoBinarySensorEntityDescription(
        key="water_flow",
        translation_key="water_flow",
        value_fn=lambda unit: unit.water_flow,
    ),
    AsekoBinarySensorEntityDescription(
        key="has_alarm",
        translation_key="alarm",
        value_fn=lambda unit: unit.has_alarm,
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    AsekoBinarySensorEntityDescription(
        key="has_error",
        translation_key="error",
        value_fn=lambda unit: unit.has_error,
        device_class=BinarySensorDeviceClass.PROBLEM,
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
    async_add_entities(
        AsekoUnitBinarySensorEntity(unit, coordinator, description)
        for unit, coordinator in data
        for description in UNIT_BINARY_SENSORS
    )


class AsekoUnitBinarySensorEntity(AsekoEntity, BinarySensorEntity):
    """Representation of a unit water flow binary sensor entity."""

    entity_description: AsekoBinarySensorEntityDescription

    def __init__(
        self,
        unit: Unit,
        coordinator: AsekoDataUpdateCoordinator,
        entity_description: AsekoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the unit binary sensor."""
        super().__init__(unit, coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._unit.serial_number}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._unit)
