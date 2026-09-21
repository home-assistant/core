"""Binary sensor platform for the Flexit integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flexit_modbus import Measurements

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlexitConfigEntry, FlexitDataCoordinator
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Flexit binary sensor entity."""

    value_fn: Callable[[Measurements], bool | None]


BINARY_SENSORS: tuple[FlexitBinarySensorEntityDescription, ...] = (
    FlexitBinarySensorEntityDescription(
        key="filter_alarm",
        translation_key="filter_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda measurements: measurements.filter_alarm,
    ),
    FlexitBinarySensorEntityDescription(
        key="electric_heater_enabled",
        translation_key="electric_heater_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda measurements: measurements.electric_heater_enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FlexitBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class FlexitBinarySensor(FlexitEntity, BinarySensorEntity):
    """Representation of a Flexit binary sensor."""

    entity_description: FlexitBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitDataCoordinator,
        entity_description: FlexitBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        assert coordinator.config_entry is not None
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.device.measurements)
