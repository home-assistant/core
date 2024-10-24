"""Support for Salda Smarty XP/XV Ventilation Unit Binary Sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SmartyConfigEntry, SmartyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Binary Sensor Platform."""

    coordinator = entry.runtime_data
    sensors = [
        AlarmSensor(coordinator),
        WarningSensor(coordinator),
        BoostSensor(coordinator),
    ]

    async_add_entities(sensors)


class SmartyBinarySensor(CoordinatorEntity[SmartyCoordinator], BinarySensorEntity):
    """Representation of a Smarty Binary Sensor."""

    def __init__(
        self,
        coordinator: SmartyCoordinator,
        name: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.config_entry.title} {name}"
        self._attr_device_class = device_class


class BoostSensor(SmartyBinarySensor):
    """Boost State Binary Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Alarm Sensor Init."""
        super().__init__(coordinator, name="Boost State", device_class=None)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_boost"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.client.boost


class AlarmSensor(SmartyBinarySensor):
    """Alarm Binary Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Alarm Sensor Init."""
        super().__init__(
            coordinator,
            name="Alarm",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_alarm"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.client.alarm


class WarningSensor(SmartyBinarySensor):
    """Warning Sensor."""

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Warning Sensor Init."""
        super().__init__(
            coordinator,
            name="Warning",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_warning"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.client.warning
