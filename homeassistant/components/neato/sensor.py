"""Support for Neato sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .entity import NeatoEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Neato sensor using config entry."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoSensor(robot))

    if not dev:
        return

    async_add_entities(dev, True)


class NeatoSensor(NeatoEntity, SensorEntity):
    """Neato sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, robot: Robot) -> None:
        """Initialize Neato sensor."""
        super().__init__(robot)
        self._attr_available = False
        self._attr_unique_id = self.robot.serial

    def update(self) -> None:
        """Update Neato Sensor."""
        try:
            state = self.robot.state
        except NeatoRobotException as ex:
            if self._attr_available:
                _LOGGER.error(
                    "Neato sensor connection error for '%s': %s", self.entity_id, ex
                )
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = state["details"]["charge"]
