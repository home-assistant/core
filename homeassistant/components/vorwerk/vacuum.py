"""Support for Neato Connected Vacuums."""
from datetime import timedelta
import logging

from pybotvac.exceptions import NeatoRobotException
import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STOP,
    StateVacuumEntity,
)
from homeassistant.const import ATTR_MODE
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    ACTION,
    ALERTS,
    ATTR_CATEGORY,
    ATTR_NAVIGATION,
    ATTR_ZONE,
    ERRORS,
    MODE,
    ROBOT_STATE_BUSY,
    ROBOT_STATE_ERROR,
    ROBOT_STATE_IDLE,
    ROBOT_STATE_PAUSE,
    SCAN_INTERVAL_MINUTES,
    VORWERK_DOMAIN,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

SUPPORT_VORWERK = (
    SUPPORT_BATTERY
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_STOP
    | SUPPORT_START
    | SUPPORT_CLEAN_SPOT
    | SUPPORT_STATE
    | SUPPORT_LOCATE
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Vorwerk vacuum with config entry."""

    _LOGGER.debug("Adding vorwerk vacuums")
    async_add_entities(
        [
            VorwerkConnectedVacuum(robot)
            for robot in hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]
        ],
        True,
    )

    platform = entity_platform.current_platform.get()
    assert platform is not None

    platform.async_register_entity_service(
        "custom_cleaning",
        {
            vol.Optional(ATTR_MODE, default=2): cv.positive_int,
            vol.Optional(ATTR_NAVIGATION, default=1): cv.positive_int,
            vol.Optional(ATTR_CATEGORY, default=4): cv.positive_int,
            vol.Optional(ATTR_ZONE): cv.string,
        },
        "vorwerk_custom_cleaning",
    )


class VorwerkConnectedVacuum(StateVacuumEntity):
    """Representation of a Vorwerk Connected Vacuum."""

    def __init__(self, robot):
        """Initialize the Vorwerk Connected Vacuum."""
        self.robot = robot
        self._available = False
        self._name = f"{self.robot.name}"
        self._robot_has_map = False
        self._robot_serial = self.robot.serial
        self._status_state = None
        self._clean_state = None
        self._state = None
        self._battery_level = None
        self._robot_boundaries = []
        self._robot_stats = None

    def update(self):
        """Update the states of Vorwerk Vacuums."""
        _LOGGER.debug("Running Vorwerk Vacuums update for '%s'", self.entity_id)
        try:
            if self._robot_stats is None:
                self._robot_stats = self.robot.get_general_info().json().get("data")
        except NeatoRobotException:
            _LOGGER.warning("Couldn't fetch robot information of %s", self.entity_id)

        try:
            self._state = self.robot.state
        except NeatoRobotException as ex:
            if self._available:  # print only once when available
                _LOGGER.error(
                    "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
                )
            self._state = None
            self._available = False
            return

        self._available = True
        _LOGGER.debug("self._state=%s", self._state)
        if "alert" in self._state:
            robot_alert = ALERTS.get(self._state["alert"])
        else:
            robot_alert = None
        if self._state["state"] == ROBOT_STATE_IDLE:
            if self._state["details"]["isCharging"]:
                self._clean_state = STATE_DOCKED
                self._status_state = "Charging"
            elif (
                self._state["details"]["isDocked"]
                and not self._state["details"]["isCharging"]
            ):
                self._clean_state = STATE_DOCKED
                self._status_state = "Docked"
            else:
                self._clean_state = STATE_IDLE
                self._status_state = "Stopped"

            if robot_alert is not None:
                self._status_state = robot_alert
        elif self._state["state"] == ROBOT_STATE_BUSY:
            if robot_alert is None:
                self._clean_state = STATE_CLEANING
                self._status_state = (
                    f"{MODE.get(self._state['cleaning']['mode'])} "
                    f"{ACTION.get(self._state['action'])}"
                )
                if (
                    "boundary" in self._state["cleaning"]
                    and "name" in self._state["cleaning"]["boundary"]
                ):
                    self._status_state += (
                        f" {self._state['cleaning']['boundary']['name']}"
                    )
            else:
                self._status_state = robot_alert
        elif self._state["state"] == ROBOT_STATE_PAUSE:
            self._clean_state = STATE_PAUSED
            self._status_state = "Paused"
        elif self._state["state"] == ROBOT_STATE_ERROR:
            self._clean_state = STATE_ERROR
            self._status_state = ERRORS.get(self._state["error"])

        self._battery_level = self._state["details"]["charge"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_VORWERK

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def available(self):
        """Return if the robot is available."""
        return self._available

    @property
    def icon(self):
        """Return specific icon."""
        return "mdi:robot-vacuum-variant"

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._clean_state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._robot_serial

    @property
    def device_state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self._status_state:
            data[ATTR_STATUS] = self._status_state

        return data

    @property
    def device_info(self):
        """Device info for robot."""
        info = {
            "identifiers": {(VORWERK_DOMAIN, self._robot_serial)},
            "name": self._name,
        }
        if self._robot_stats:
            info["manufacturer"] = self._robot_stats["battery"]["vendor"]
            info["model"] = self._robot_stats["model"]
            info["sw_version"] = self._robot_stats["firmware"]
        return info

    def start(self):
        """Start cleaning or resume cleaning."""
        try:
            if self._state["state"] == ROBOT_STATE_IDLE:
                self.robot.start_cleaning()
            elif self._state["state"] == ROBOT_STATE_PAUSE:
                self.robot.resume_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def pause(self):
        """Pause the vacuum."""
        try:
            self.robot.pause_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        try:
            if self._clean_state == STATE_CLEANING:
                self.robot.pause_cleaning()
            self._clean_state = STATE_RETURNING
            self.robot.send_to_base()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        try:
            self.robot.stop_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def locate(self, **kwargs):
        """Locate the robot by making it emit a sound."""
        try:
            self.robot.locate()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def clean_spot(self, **kwargs):
        """Run a spot cleaning starting from the base."""
        try:
            self.robot.start_spot_cleaning()
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    def vorwerk_custom_cleaning(self, mode, navigation, category, zone=None):
        """Zone cleaning service call."""
        boundary_id = None
        if zone is not None:
            for boundary in self._robot_boundaries:
                if zone in boundary["name"]:
                    boundary_id = boundary["id"]
            if boundary_id is None:
                _LOGGER.error(
                    "Zone '%s' was not found for the robot '%s'", zone, self.entity_id
                )
                return

        self._clean_state = STATE_CLEANING
        try:
            self.robot.start_cleaning(mode, navigation, category, boundary_id)
        except NeatoRobotException as ex:
            _LOGGER.error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )
