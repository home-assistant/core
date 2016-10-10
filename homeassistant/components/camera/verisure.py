"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.verisure/
"""
import logging
import os

from datetime import timedelta
from homeassistant.components.camera import Camera
from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import CONF_SMARTCAM
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Verisure File'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    if not int(hub.config.get(CONF_SMARTCAM, 1)):
        return False
    smartcam_dict = {}
    _LOGGER.debug('loading initial smartcam dict')
    smartcam_dict = hub.my_pages.smartcam.get_imagelist()
    _LOGGER.debug('smartcam_dict=%s', smartcam_dict)
    if not smartcam_dict:
        return False
    device_id = list(smartcam_dict.keys())
    file_path = os.path.join(hass.config.config_dir)
    if not os.access(file_path, os.R_OK):
        _LOGGER.error("file path %s is not readable", file_path)
        return False
    for device_id in smartcam_dict:
        add_devices([VerisureFile(device_id, file_path, smartcam_dict)])


# pylint: disable=too-many-instance-attributes
class VerisureFile(Camera):
    """Local camera."""

    def __init__(self, device_id, file_path, smartcam_dict):
        """Initialize Verisure File Camera component."""
        super().__init__()

        self._delete_image = None
        self._device_id = device_id
        self._file_path = file_path
        self._new_image_id = None
        self._image_id = None
        self._image = None
        self._smartcam_dict = smartcam_dict
        self._smartcam_old_dict = {}
        self._images = []
        _LOGGER.debug('self._smartcam_dict=%s, self._file_path=%s',
                      self._smartcam_dict, self._file_path)

    def camera_image(self):
        """Return image response."""
        self.check_imagelist()
        _LOGGER.debug('trying to open %s', self._image)
        with open(self._image, 'rb') as file:
            return file.read()

    def check_imagelist(self):
        """Check the contents of the image list."""
        self.update_imagelist()
        if self._smartcam_old_dict == self._smartcam_dict:
            _LOGGER.debug('old and new dict is equal')
            return
        else:
            for self._device_id in self._smartcam_dict:
                self._images = list(self._smartcam_dict.items())
                self._new_image_id = self._images[0][1][0]
                _LOGGER.debug('self._device_id=%s, self._images=%s, '
                              'self._new_image_id=%s', self._device_id,
                              self._images, self._new_image_id)
                if self._new_image_id == '-1' or \
                   self._image_id == self._new_image_id:
                    _LOGGER.debug('The image is the same, or loading image_id')
                    return
                else:
                    _LOGGER.debug('Download new image %s', self._new_image_id)
                    hub.my_pages.smartcam.download_image(self._device_id,
                                                         self._new_image_id,
                                                         self._file_path)
                    self._smartcam_old_dict = self._smartcam_dict
                    if self._image_id:
                        _LOGGER.debug('self._image_id=%s', self._image_id)
                        self._delete_image = os.path.join(self._file_path,
                                                          '{}{}'.format(
                                                              self._image_id,
                                                              '.jpg'))
                        _LOGGER.debug('Deleting %s', self._delete_image)
                        os.remove(self._delete_image)
                        self._image_id = self._new_image_id
                        self._image = os.path.join(self._file_path,
                                                   '{}{}'.format(
                                                       self._image_id,
                                                       '.jpg'))
                    else:
                        self._image = os.path.join(self._file_path,
                                                   '{}{}'.format(
                                                       self._new_image_id,
                                                       '.jpg'))
                        self._image_id = self._new_image_id

    @Throttle(timedelta(seconds=30))
    def update_imagelist(self):
        """Update the imagelist for the camera."""
        _LOGGER.debug('Running update imagelist')
        self._smartcam_dict = hub.my_pages.smartcam.get_imagelist()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._device_id
