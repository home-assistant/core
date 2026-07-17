"""Sensor platform for the Nespresso integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from nespresso_ble import MachineStatus, NespressoDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NespressoBLEConfigEntry, NespressoBLECoordinator
from .entity import NespressoBLEEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NespressoBLESensorEntityDescription(SensorEntityDescription):
    """Describes a Nespresso sensor entity."""

    value_fn: Callable[[NespressoDevice], StateType]


SENSORS: tuple[NespressoBLESensorEntityDescription, ...] = (
    NespressoBLESensorEntityDescription(
        key="machine_status",
        translation_key="machine_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in MachineStatus],
        value_fn=lambda device: device.status.value,
    ),
    NespressoBLESensorEntityDescription(
        key="water_hardness",
        translation_key="water_hardness",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            device.water_hardness.value if device.water_hardness is not None else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NespressoBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nespresso sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        NespressoBLESensor(coordinator, description) for description in SENSORS
    )


class NespressoBLESensor(NespressoBLEEntity, SensorEntity):
    """A Nespresso sensor."""

    entity_description: NespressoBLESensorEntityDescription

    def __init__(
        self,
        coordinator: NespressoBLECoordinator,
        description: NespressoBLESensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.address}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
