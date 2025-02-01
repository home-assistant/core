"""Support for Neato Connected Vacuums switches."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_LOGIN, NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .entity import NeatoEntity
from .hub import NeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

SWITCH_TYPE_SCHEDULE = "schedule"

SWITCH_TYPES = {SWITCH_TYPE_SCHEDULE: ["Schedule"]}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato switch with config entry."""
    neato: NeatoHub = hass.data[NEATO_LOGIN]
    dev = [
        NeatoConnectedSwitch(neato, robot, type_name)
        for robot in hass.data[NEATO_ROBOTS]
        for type_name in SWITCH_TYPES
    ]

    if not dev:
        return

    _LOGGER.debug("Adding switches %s", dev)
    async_add_entities(dev, True)


class NeatoConnectedSwitch(NeatoEntity, SwitchEntity):
    """Neato Connected Switches."""

    _attr_translation_key = "schedule"
    _attr_available = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, neato: NeatoHub, robot: Robot, switch_type: str) -> None:
        """Initialize the Neato Connected switches."""
        super().__init__(robot)
        self.type = switch_type
        self._state: dict[str, Any] | None = None
        self._schedule_state: str | None = None
        self._clean_state = None
        self._attr_unique_id = self.robot.serial

    def update(self) -> None:
        """Update the states of Neato switches."""
        _LOGGER.debug("Running Neato switch update for '%s'", self.entity_id)
        try:
            self._state = self.robot.state
        except NeatoRobotException as ex:
            if self._attr_available:  # Print only once when available
                _LOGGER.error(
                    "Neato switch connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._attr_available = False
            return

        self._attr_available = True
        _LOGGER.debug("self._state=%s", self._state)
        if self.type == SWITCH_TYPE_SCHEDULE:
            _LOGGER.debug("State: %s", self._state)
            if self._state is not None and self._state["details"]["isScheduleEnabled"]:
                self._schedule_state = STATE_ON
            else:
                self._schedule_state = STATE_OFF
            _LOGGER.debug(
                "Schedule state for '%s': %s", self.entity_id, self._schedule_state
            )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(
            self.type == SWITCH_TYPE_SCHEDULE and self._schedule_state == STATE_ON
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            try:
                self.robot.enable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Neato switch connection error '%s': %s", self.entity_id, ex
                )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            try:
                self.robot.disable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Neato switch connection error '%s': %s", self.entity_id, ex
                )
