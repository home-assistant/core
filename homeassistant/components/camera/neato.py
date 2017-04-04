"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.neato/
"""
import errno
import logging
import os

from homeassistant.components.camera import Camera
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.neato import (
    NEATO_MAP_DATA, NEATO_ROBOTS, NEATO_LOGIN)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    if not hass.data[NEATO_ROBOTS]:
        return False
    directory_path = hass.config.config_dir
    if not os.access(directory_path, os.R_OK):
        _LOGGER.error("file path %s is not readable", directory_path)
        return False
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        if 'maps' not in robot.traits:
            return False
        dev.append(NeatoCleaningMap(hass, robot, directory_path))
    _LOGGER.debug('Adding robots for cleaning maps %s', dev)
    directory_path = hass.config.config_dir
    add_devices(dev)


class NeatoCleaningMap(Camera):
    """Neato cleaning map for last clean."""

    def __init__(self, hass, robot, directory_path):
        """Initialize Neato cleaning map."""
        super().__init__()
        self.robot = robot
        self._robot_name = self.robot.name + ' Cleaning Map'
        self._robot_serial = self.robot.serial
        self._directory_path = directory_path
        self.neato = hass.data[NEATO_LOGIN]
        self._map_data = hass.data[NEATO_MAP_DATA]
        self._image_url = None
        self._filename = None
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             self.delete_image)

    def camera_image(self):
        """Return image response."""
        self.check_maps()
        if not self._image_url:
            _LOGGER.debug('No image to display')
            return
        display_image = os.path.join(self._directory_path, self._filename)
        _LOGGER.debug('Trying to open %s', display_image)
        with open(display_image, 'rb') as file:
            return file.read()

    def check_maps(self):
        """Check the contents of the map list."""
        self.neato.update_robots()
        if not self._map_data:
            return
        image_url = self._map_data[self._robot_serial]['maps'][0]['url']
        if image_url == self._image_url:
            _LOGGER.debug('The map image is the same as old')
            return
        _LOGGER.debug('Download new map image %s', image_url)
        self.neato.download_map(image_url, self._directory_path)
        if self._image_url:
            self.delete_image(self)
            _LOGGER.debug('Old map image %s', self._image_url)

        self._image_url = image_url
        part_filename = (
            image_url.rsplit('/', 2)[1] + '-' + image_url.rsplit('/', 1)[1])
        self._filename = part_filename.split('?')[0]

    def delete_image(self, event):
        """Delete an old image."""
        remove_image = os.path.join(self._directory_path, self._filename)
        try:
            os.remove(remove_image)
            _LOGGER.debug('Deleting old map image %s', remove_image)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise

    @property
    def name(self):
        """Return the name of this camera."""
        return self._robot_name
