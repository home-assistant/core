"""Support for Neato Connected Vacuums switches."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_DOMAIN, NEATO_LOGIN, NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .hub import NeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

SWITCH_TYPE_SCHEDULE = "schedule"

SWITCH_TYPES = {SWITCH_TYPE_SCHEDULE: ["Schedule"]}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato switch with config entry."""
    dev = []
    neato: NeatoHub = hass.data[NEATO_LOGIN]

    for robot in hass.data[NEATO_ROBOTS]:
        for type_name in SWITCH_TYPES:
            dev.append(NeatoConnectedSwitch(neato, robot, type_name))

    if not dev:
        return

    _LOGGER.debug("Adding switches %s", dev)
    async_add_entities(dev, True)


class NeatoConnectedSwitch(SwitchEntity):
    """Neato Connected Switches."""

    def __init__(self, neato: NeatoHub, robot: Robot, switch_type: str) -> None:
        """Initialize the Neato Connected switches."""
        self.type = switch_type
        self.robot = robot
        self._available = False
        self._robot_name = f"{self.robot.name} {SWITCH_TYPES[self.type][0]}"
        self._state: dict[str, Any] | None = None
        self._schedule_state: str | None = None
        self._clean_state = None
        self._robot_serial: str = self.robot.serial

    def update(self) -> None:
        """Update the states of Neato switches."""
        _LOGGER.debug("Running Neato switch update for '%s'", self.entity_id)
        try:
            self._state = self.robot.state
        except NeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato switch connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._available = False
            return

        self._available = True
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
    def name(self) -> str:
        """Return the name of the switch."""
        return self._robot_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._robot_serial

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(
            self.type == SWITCH_TYPE_SCHEDULE and self._schedule_state == STATE_ON
        )

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.CONFIG

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for neato robot."""
        return DeviceInfo(identifiers={(NEATO_DOMAIN, self._robot_serial)})

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
