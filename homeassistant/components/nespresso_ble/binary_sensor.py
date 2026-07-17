"""Binary sensor platform for the Nespresso integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from nespresso_ble import NespressoDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NespressoBLEConfigEntry, NespressoBLECoordinator
from .entity import NespressoBLEEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NespressoBLEBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Nespresso binary sensor entity."""

    value_fn: Callable[[NespressoDevice], bool | None]
    exists_fn: Callable[[NespressoDevice], bool] = lambda _device: True


BINARY_SENSORS: tuple[NespressoBLEBinarySensorEntityDescription, ...] = (
    NespressoBLEBinarySensorEntityDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.error,
    ),
    NespressoBLEBinarySensorEntityDescription(
        key="descaling_needed",
        translation_key="descaling_needed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.descaling_needed,
        exists_fn=lambda device: device.descaling_needed is not None,
    ),
    NespressoBLEBinarySensorEntityDescription(
        key="water_tank_empty",
        translation_key="water_tank_empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.water_tank_empty,
        exists_fn=lambda device: device.water_tank_empty is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NespressoBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nespresso binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        NespressoBLEBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(coordinator.data)
    )


class NespressoBLEBinarySensor(NespressoBLEEntity, BinarySensorEntity):
    """A Nespresso binary sensor."""

    entity_description: NespressoBLEBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NespressoBLECoordinator,
        description: NespressoBLEBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.address}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
