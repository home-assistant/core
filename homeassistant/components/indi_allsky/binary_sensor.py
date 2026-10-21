"""Support for INDI Allsky binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    IndiAllSkyConfigEntry,
    IndiAllSkyData,
    IndiAllSkyDataUpdateCoordinator,
)
from .entity import IndiAllSkyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndiAllSkyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing INDI Allsky binary sensor entities."""

    is_on_fn: Callable[[IndiAllSkyData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[IndiAllSkyBinarySensorEntityDescription, ...] = (
    IndiAllSkyBinarySensorEntityDescription(
        key="night",
        translation_key="night",
        is_on_fn=lambda data: data.exposure.night if data.exposure else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up INDI Allsky binary sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        IndiAllSkyBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class IndiAllSkyBinarySensor(IndiAllSkyEntity, BinarySensorEntity):
    """Representation of an INDI Allsky binary sensor."""

    entity_description: IndiAllSkyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
        description: IndiAllSkyBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
