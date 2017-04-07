"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.neato/
"""
import logging

from homeassistant.components.camera import Camera
from homeassistant.components.neato import (
    NEATO_MAP_DATA, NEATO_ROBOTS, NEATO_LOGIN)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        if 'maps' in robot.traits:
            dev.append(NeatoCleaningMap(hass, robot))
    _LOGGER.debug('Adding robots for cleaning maps %s', dev)
    add_devices(dev)


class NeatoCleaningMap(Camera):
    """Neato cleaning map for last clean."""

    def __init__(self, hass, robot):
        """Initialize Neato cleaning map."""
        super().__init__()
        self.robot = robot
        self._robot_name = self.robot.name + ' Cleaning Map'
        self._robot_serial = self.robot.serial
        self.neato = hass.data[NEATO_LOGIN]
        self._map_data = hass.data[NEATO_MAP_DATA]
        self._image_url = self._map_data[self._robot_serial]['maps'][0]['url']
        image = self.neato.download_map(self._image_url)
        self._image = image.read()

    def camera_image(self):
        """Return image response."""
        self.check_maps()
        if not self._image_url:
            _LOGGER.debug('No image to display')
            return
        _LOGGER.debug('Displaying: %s', self._image)
        return self._image

    def check_maps(self):
        """Check the contents of the map list."""
        self.neato.update_robots()
        image = None
        image_url = self._map_data[self._robot_serial]['maps'][0]['url']
        if image_url == self._image_url:
            _LOGGER.debug('The map image_url is the same as old')
            return
        image = self.neato.download_map(image_url)
        self._image = image.read()
        self._image_url = image_url

    @property
    def name(self):
        """Return the name of this camera."""
        return self._robot_name
