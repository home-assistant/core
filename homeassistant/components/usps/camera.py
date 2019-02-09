"""
Support for a camera made up of usps mail images.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera.usps/
"""
from datetime import timedelta
import logging

from homeassistant.components.camera import Camera
from homeassistant.components.usps import DATA_USPS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['usps']

SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up USPS mail camera."""
    if discovery_info is None:
        return

    usps = hass.data[DATA_USPS]
    add_entities([USPSCamera(usps)])


class USPSCamera(Camera):
    """Representation of the images available from USPS."""

    def __init__(self, usps):
        """Initialize the USPS camera images."""
        super().__init__()

        self._usps = usps
        self._name = self._usps.name
        self._session = self._usps.session

        self._mail_img = []
        self._last_mail = None
        self._mail_index = 0
        self._mail_count = 0

        self._timer = None

    def camera_image(self):
        """Update the camera's image if it has changed."""
        self._usps.update()
        try:
            self._mail_count = len(self._usps.mail)
        except TypeError:
            # No mail
            return None

        if self._usps.mail != self._last_mail:
            # Mail items must have changed
            self._mail_img = []
            if len(self._usps.mail) >= 1:
                self._last_mail = self._usps.mail
                for article in self._usps.mail:
                    _LOGGER.debug("Fetching article image: %s", article)
                    img = self._session.get(article['image']).content
                    self._mail_img.append(img)

        try:
            return self._mail_img[self._mail_index]
        except IndexError:
            return None

    @property
    def name(self):
        """Return the name of this camera."""
        return '{} mail'.format(self._name)

    @property
    def model(self):
        """Return date of mail as model."""
        try:
            return 'Date: {}'.format(str(self._usps.mail[0]['date']))
        except IndexError:
            return None

    @property
    def should_poll(self):
        """Update the mail image index periodically."""
        return True

    def update(self):
        """Update mail image index."""
        if self._mail_index < (self._mail_count - 1):
            self._mail_index += 1
        else:
            self._mail_index = 0
