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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PeblarConfigEntry, PeblarData, PeblarDataUpdateCoordinator


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
        PeblarBinarySensorEntity(entry=entry, description=description)
        for description in DESCRIPTIONS
    )


class PeblarBinarySensorEntity(
    CoordinatorEntity[PeblarDataUpdateCoordinator], BinarySensorEntity
):
    """Defines a Peblar binary sensor entity."""

    entity_description: PeblarBinarySensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(entry.runtime_data.data_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )

    @property
    def is_on(self) -> bool:
        """Return state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
