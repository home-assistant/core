"""Support for Neato sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_LOGIN, NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .entity import NeatoEntity
from .hub import NeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

BATTERY = "Battery"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Neato sensor using config entry."""
    dev = []
    neato: NeatoHub = hass.data[NEATO_LOGIN]
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoSensor(neato, robot))

    if not dev:
        return

    _LOGGER.debug("Adding robots for sensors %s", dev)
    async_add_entities(dev, True)


class NeatoSensor(NeatoEntity, SensorEntity):
    """Neato sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_available: bool = False

    def __init__(self, neato: NeatoHub, robot: Robot) -> None:
        """Initialize Neato sensor."""
        super().__init__(robot)
        self._robot_serial: str = self.robot.serial
        self._attr_unique_id = self.robot.serial
        self._state: dict[str, Any] | None = None

    def update(self) -> None:
        """Update Neato Sensor."""
        try:
            self._state = self.robot.state
        except NeatoRobotException as ex:
            if self._attr_available:
                _LOGGER.error(
                    "Neato sensor connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._attr_available = False
            return

        self._attr_available = True
        _LOGGER.debug("self._state=%s", self._state)

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if self._state is not None:
            return str(self._state["details"]["charge"])
        return None
