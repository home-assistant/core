"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.verisure/
"""
import errno
import logging
import os

from homeassistant.components.camera import Camera
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import CONF_SMARTCAM

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Verisure Camera."""
    if not int(hub.config.get(CONF_SMARTCAM, 1)):
        return False
    directory_path = hass.config.config_dir
    if not os.access(directory_path, os.R_OK):
        _LOGGER.error("file path %s is not readable", directory_path)
        return False
    hub.update_smartcam()
    smartcams = []
    smartcams.extend([
        VerisureSmartcam(hass, value.deviceLabel, directory_path)
        for value in hub.smartcam_status.values()])
    add_devices(smartcams)


class VerisureSmartcam(Camera):
    """Representation of a Verisure camera."""

    def __init__(self, hass, device_id, directory_path):
        """Initialize Verisure File Camera component."""
        super().__init__()

        self._device_id = device_id
        self._directory_path = directory_path
        self._image = None
        self._image_id = None
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             self.delete_image)

    def camera_image(self):
        """Return image response."""
        self.check_imagelist()
        if not self._image:
            _LOGGER.debug("No image to display")
            return
        _LOGGER.debug("Trying to open %s", self._image)
        with open(self._image, 'rb') as file:
            return file.read()

    def check_imagelist(self):
        """Check the contents of the image list."""
        hub.update_smartcam_imagelist()
        if (self._device_id not in hub.smartcam_dict or
                not hub.smartcam_dict[self._device_id]):
            return
        images = hub.smartcam_dict[self._device_id]
        new_image_id = images[0]
        _LOGGER.debug("self._device_id=%s, self._images=%s, "
                      "self._new_image_id=%s", self._device_id,
                      images, new_image_id)
        if (new_image_id == '-1' or
                self._image_id == new_image_id):
            _LOGGER.debug("The image is the same, or loading image_id")
            return
        _LOGGER.debug("Download new image %s", new_image_id)
        hub.my_pages.smartcam.download_image(
            self._device_id, new_image_id, self._directory_path)
        _LOGGER.debug("Old image_id=%s", self._image_id)
        self.delete_image(self)

        self._image_id = new_image_id
        self._image = os.path.join(
            self._directory_path, '{}{}'.format(self._image_id, '.jpg'))

    def delete_image(self, event):
        """Delete an old image."""
        remove_image = os.path.join(
            self._directory_path, '{}{}'.format(self._image_id, '.jpg'))
        try:
            os.remove(remove_image)
            _LOGGER.debug("Deleting old image %s", remove_image)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise

    @property
    def name(self):
        """Return the name of this camera."""
        return hub.smartcam_status[self._device_id].location
