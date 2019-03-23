"""Support for loading picture from Neato."""
from datetime import timedelta
import logging

from homeassistant.components.camera import Camera

from . import NEATO_LOGIN, NEATO_MAP_DATA, NEATO_ROBOTS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']

SCAN_INTERVAL = timedelta(minutes=10)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Neato Camera."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        if 'maps' in robot.traits:
            dev.append(NeatoCleaningMap(hass, robot))
    _LOGGER.debug("Adding robots for cleaning maps %s", dev)
    add_entities(dev, True)


class NeatoCleaningMap(Camera):
    """Neato cleaning map for last clean."""

    def __init__(self, hass, robot):
        """Initialize Neato cleaning map."""
        super().__init__()
        self.robot = robot
        self._robot_name = '{} {}'.format(self.robot.name, 'Cleaning Map')
        self._robot_serial = self.robot.serial
        self.neato = hass.data[NEATO_LOGIN]
        self._image_url = None
        self._image = None

    def camera_image(self):
        """Return image response."""
        self.update()
        return self._image

    def update(self):
        """Check the contents of the map list."""
        self.neato.update_robots()
        image_url = None
        map_data = self.hass.data[NEATO_MAP_DATA]
        image_url = map_data[self._robot_serial]['maps'][0]['url']
        if image_url == self._image_url:
            _LOGGER.debug("The map image_url is the same as old")
            return
        image = self.neato.download_map(image_url)
        self._image = image.read()
        self._image_url = image_url

    @property
    def name(self):
        """Return the name of this camera."""
        return self._robot_name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._robot_serial
