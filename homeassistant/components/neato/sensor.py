"""Support for Neato sensors."""
import logging

from datetime import timedelta
from pybotvac.exceptions import NeatoRobotException

from homeassistant.components.sensor import DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity

from .const import NEATO_ROBOTS, NEATO_LOGIN, NEATO_DOMAIN, SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)

BATTERY = "Battery"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Neato sensor."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Neato sensor using config entry."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoSensor(hass, robot))

    if not dev:
        return

    _LOGGER.debug("Adding robots for sensors %s", dev)
    async_add_entities(dev, True)


class NeatoSensor(Entity):
    """Neato sensor."""

    def __init__(self, hass, robot):
        """Initialize Neato sensor."""
        super().__init__()
        self.robot = robot
        self.neato = hass.data[NEATO_LOGIN] if NEATO_LOGIN in hass.data else None
        self._available = self.neato.logged_in if self.neato is not None else False
        self._robot_name = f"{self.robot.name} {BATTERY}"
        self._robot_serial = self.robot.serial
        self._state = None

    def update(self):
        """Update Neato Sensor."""
        if self.neato is None:
            _LOGGER.error("Error while updating sensor")
            self._state = None
            self._available = False
            return

        try:
            self.neato.update_robots()
            self._state = self.robot.state
            if not self._available:
                _LOGGER.warning("Neato sensor is back online")
            self._available = True
        except NeatoRobotException as ex:
            _LOGGER.warning("Neato sensor connection error: %s", ex)
            self._state = None
            self._available = False
            return
        _LOGGER.debug("self._state=%s", self._state)

    @property
    def name(self):
        """Return the name of this sensor."""
        return self._robot_name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._robot_serial

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def available(self):
        """Return availability."""
        return self._available

    @property
    def state(self):
        """Return the state."""
        return self._state["details"]["charge"]

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return "%"

    @property
    def device_info(self):
        """Device info for neato robot."""
        return {"identifiers": {(NEATO_DOMAIN, self._robot_serial)}}
