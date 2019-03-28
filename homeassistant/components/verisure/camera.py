"""Support for Verisure cameras."""
import errno
import logging
import os

from homeassistant.components.camera import Camera
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from . import CONF_SMARTCAM, HUB as hub

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure Camera."""
    if not int(hub.config.get(CONF_SMARTCAM, 1)):
        return False
    directory_path = hass.config.config_dir
    if not os.access(directory_path, os.R_OK):
        _LOGGER.error("file path %s is not readable", directory_path)
        return False
    hub.update_overview()
    smartcams = []
    smartcams.extend([
        VerisureSmartcam(hass, device_label, directory_path)
        for device_label in hub.get(
            "$.customerImageCameras[*].deviceLabel")])
    add_entities(smartcams)


class VerisureSmartcam(Camera):
    """Representation of a Verisure camera."""

    def __init__(self, hass, device_label, directory_path):
        """Initialize Verisure File Camera component."""
        super().__init__()

        self._device_label = device_label
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
        hub.update_smartcam_imageseries()
        image_ids = hub.get_image_info(
            "$.imageSeries[?(@.deviceLabel=='%s')].image[0].imageId",
            self._device_label)
        if not image_ids:
            return
        new_image_id = image_ids[0]
        if new_image_id in ('-1', self._image_id):
            _LOGGER.debug("The image is the same, or loading image_id")
            return
        _LOGGER.debug("Download new image %s", new_image_id)
        new_image_path = os.path.join(
            self._directory_path, '{}{}'.format(new_image_id, '.jpg'))
        hub.session.download_image(
            self._device_label, new_image_id, new_image_path)
        _LOGGER.debug("Old image_id=%s", self._image_id)
        self.delete_image(self)

        self._image_id = new_image_id
        self._image = new_image_path

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
        return hub.get_first(
            "$.customerImageCameras[?(@.deviceLabel=='%s')].area",
            self._device_label)
