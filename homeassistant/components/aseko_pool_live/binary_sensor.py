"""Support for Aseko Pool Live binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioaseko import Unit

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AsekoConfigEntry
from .entity import AsekoEntity


@dataclass(frozen=True, kw_only=True)
class AsekoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Aseko binary sensor entity."""

    value_fn: Callable[[Unit], bool | None]


BINARY_SENSORS: tuple[AsekoBinarySensorEntityDescription, ...] = (
    AsekoBinarySensorEntityDescription(
        key="water_flow",
        translation_key="water_flow_to_probes",
        value_fn=lambda unit: unit.water_flow_to_probes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AsekoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Aseko Pool Live binary sensors."""
    coordinator = config_entry.runtime_data
    units = coordinator.data.values()
    async_add_entities(
        AsekoBinarySensorEntity(unit, coordinator, description)
        for description in BINARY_SENSORS
        for unit in units
        if description.value_fn(unit) is not None
    )


class AsekoBinarySensorEntity(AsekoEntity, BinarySensorEntity):
    """Representation of an Aseko binary sensor entity."""

    entity_description: AsekoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.unit)
