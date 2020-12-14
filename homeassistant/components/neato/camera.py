"""Support for loading picture from Neato."""
from datetime import timedelta
import logging

from pybotvac.exceptions import NeatoRobotException

from homeassistant.components.camera import Camera

from .const import (
    NEATO_DOMAIN,
    NEATO_LOGIN,
    NEATO_MAP_DATA,
    NEATO_ROBOTS,
    SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)
ATTR_GENERATED_AT = "generated_at"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Neato camera with config entry."""
    dev = []
    neato = hass.data.get(NEATO_LOGIN)
    mapdata = hass.data.get(NEATO_MAP_DATA)
    for robot in hass.data[NEATO_ROBOTS]:
        if "maps" in robot.traits:
            dev.append(NeatoCleaningMap(neato, robot, mapdata))

    if not dev:
        return

    _LOGGER.debug("Adding robots for cleaning maps %s", dev)
    async_add_entities(dev, True)


class NeatoCleaningMap(Camera):
    """Neato cleaning map for last clean."""

    def __init__(self, neato, robot, mapdata):
        """Initialize Neato cleaning map."""
        super().__init__()
        self.robot = robot
        self.neato = neato
        self._mapdata = mapdata
        self._available = self.neato.logged_in if self.neato is not None else False
        self._robot_name = f"{self.robot.name} Cleaning Map"
        self._robot_serial = self.robot.serial
        self._generated_at = None
        self._image_url = None
        self._image = None

    def camera_image(self):
        """Return image response."""
        self.update()
        return self._image

    def update(self):
        """Check the contents of the map list."""
        if self.neato is None:
            _LOGGER.error("Error while updating '%s'", self.entity_id)
            self._image = None
            self._image_url = None
            self._available = False
            return

        _LOGGER.debug("Running camera update for '%s'", self.entity_id)
        try:
            self.neato.update_robots()
        except NeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._image_url = None
            self._available = False
            return

        image_url = None
        map_data = self._mapdata[self._robot_serial]["maps"][0]
        image_url = map_data["url"]
        if image_url == self._image_url:
            _LOGGER.debug(
                "The map image_url for '%s' is the same as old", self.entity_id
            )
            return

        try:
            image = self.neato.download_map(image_url)
        except NeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._image_url = None
            self._available = False
            return

        self._image = image.read()
        self._image_url = image_url
        self._generated_at = (map_data["generated_at"].strip("Z")).replace("T", " ")
        self._available = True

    @property
    def name(self):
        """Return the name of this camera."""
        return self._robot_name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._robot_serial

    @property
    def available(self):
        """Return if the robot is available."""
        return self._available

    @property
    def device_info(self):
        """Device info for neato robot."""
        return {"identifiers": {(NEATO_DOMAIN, self._robot_serial)}}

    @property
    def device_state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self._generated_at is not None:
            data[ATTR_GENERATED_AT] = self._generated_at

        return data
