"""Support for Neato Connected Vacuums switches."""
from datetime import timedelta
import logging

from pybotvac.exceptions import NeatoRobotException

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity import ToggleEntity

from .const import NEATO_DOMAIN, NEATO_LOGIN, NEATO_ROBOTS, SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

SWITCH_TYPE_SCHEDULE = "schedule"

SWITCH_TYPES = {SWITCH_TYPE_SCHEDULE: ["Schedule"]}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Neato switch with config entry."""
    dev = []
    neato = hass.data.get(NEATO_LOGIN)
    for robot in hass.data[NEATO_ROBOTS]:
        for type_name in SWITCH_TYPES:
            dev.append(NeatoConnectedSwitch(neato, robot, type_name))

    if not dev:
        return

    _LOGGER.debug("Adding switches %s", dev)
    async_add_entities(dev, True)


class NeatoConnectedSwitch(ToggleEntity):
    """Neato Connected Switches."""

    def __init__(self, neato, robot, switch_type):
        """Initialize the Neato Connected switches."""
        self.type = switch_type
        self.robot = robot
        self._available = False
        self._robot_name = f"{self.robot.name} {SWITCH_TYPES[self.type][0]}"
        self._state = None
        self._schedule_state = None
        self._clean_state = None
        self._robot_serial = self.robot.serial

    def update(self):
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
            if self._state["details"]["isScheduleEnabled"]:
                self._schedule_state = STATE_ON
            else:
                self._schedule_state = STATE_OFF
            _LOGGER.debug(
                "Schedule state for '%s': %s", self.entity_id, self._schedule_state
            )

    @property
    def name(self):
        """Return the name of the switch."""
        return self._robot_name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._robot_serial

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            if self._schedule_state == STATE_ON:
                return True
            return False

    @property
    def device_info(self):
        """Device info for neato robot."""
        return {"identifiers": {(NEATO_DOMAIN, self._robot_serial)}}

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            try:
                self.robot.enable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Neato switch connection error '%s': %s", self.entity_id, ex
                )

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            try:
                self.robot.disable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Neato switch connection error '%s': %s", self.entity_id, ex
                )
