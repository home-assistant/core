"""Support for Peblar binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PeblarConfigEntry, PeblarData, PeblarDataUpdateCoordinator
from .entity import PeblarEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PeblarBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Peblar binary sensor entities."""

    is_on_fn: Callable[[PeblarData], bool]


DESCRIPTIONS = [
    PeblarBinarySensorEntityDescription(
        key="active_error_codes",
        translation_key="active_error_codes",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda x: bool(x.system.active_error_codes),
    ),
    PeblarBinarySensorEntityDescription(
        key="active_warning_codes",
        translation_key="active_warning_codes",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda x: bool(x.system.active_warning_codes),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar binary sensor based on a config entry."""
    async_add_entities(
        PeblarBinarySensorEntity(
            entry=entry,
            coordinator=entry.runtime_data.data_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarBinarySensorEntity(
    PeblarEntity[PeblarDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Defines a Peblar binary sensor entity."""

    entity_description: PeblarBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
