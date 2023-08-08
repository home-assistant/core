"""Support for Neato Connected Vacuums switches."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .entity import NeatoEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato switch with config entry."""
    dev = []

    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoConnectedSwitch(robot))

    if not dev:
        return

    async_add_entities(dev, True)


class NeatoConnectedSwitch(NeatoEntity, SwitchEntity):
    """Neato Connected Switches."""

    _attr_translation_key = "schedule"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, robot: Robot) -> None:
        """Initialize the Neato Connected switches."""
        super().__init__(robot)
        self._attr_unique_id = self.robot.serial
        self._attr_available = False

    def update(self) -> None:
        """Update the states of Neato switches."""
        _LOGGER.debug("Running Neato switch update for '%s'", self.entity_id)
        try:
            state = self.robot.state
        except NeatoRobotException as ex:
            if self._attr_available:  # Print only once when available
                _LOGGER.error(
                    "Neato switch connection error for '%s': %s", self.entity_id, ex
                )
            self._attr_available = False
            return

        self._attr_available = True
        _LOGGER.debug("State: %s", state)
        self._attr_is_on = state["details"]["isScheduleEnabled"]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            self.robot.enable_schedule()
        except NeatoRobotException as ex:
            _LOGGER.error("Neato switch connection error '%s': %s", self.entity_id, ex)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            self.robot.disable_schedule()
        except NeatoRobotException as ex:
            _LOGGER.error("Neato switch connection error '%s': %s", self.entity_id, ex)
