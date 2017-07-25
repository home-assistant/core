"""
Support for a camera made up of usps mail images.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera.usps/
"""
import logging
from datetime import timedelta

from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow
from homeassistant.components.usps import DATA_USPS
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['usps']

NOMAIL_IMAGE_PATH = 'http://imgur.com/a/bZc6n'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up USPS mail camera."""
    if discovery_info is None:
        return

    usps = hass.data[DATA_USPS]
    add_devices([USPSCamera(hass, usps)])


class USPSCamera(Camera):
    """Representation of the images available from USPS."""

    def __init__(self, hass, usps):
        """Initialize the USPS camera images."""
        super(USPSCamera, self).__init__()

        self._hass = hass
        self._usps = usps
        self._name = self._usps.name
        self._session = self._usps.session

        self._mail_img = []
        self._last_mail = None
        self._mail_index = 0
        self._mail_count = 0

        self._no_mail_img = self.no_mail_image()

        self._timer = None

    def no_mail_image(self):
        """Fetch no mail camera image."""
        img = self._session.get(NOMAIL_IMAGE_PATH).content
        return img

    def camera_image(self):
        """Update the camera's image if it has changed."""
        try:
            self._mail_count = len(self._usps.mail)
        except TypeError:
            # No mail
            return self._no_mail_img

        if self._usps.mail != self._last_mail:
            # Mail items must have changed
            self._mail_img = []
            if self._usps.mail is not None and len(self._usps.mail) >= 1:
                self._last_mail = self._usps.mail
                for article in self._usps.mail:
                    _LOGGER.debug("Fetching article image: %s", article)
                    img = self._session.get(article['image']).content
                    self._mail_img.append(img)

        def _interval_update(now):
            """Timer callback for increasing index."""
            if self._mail_index < (self._mail_count - 1):
                self._mail_index += 1
            else:
                self._mail_index = 0
            # Reset Timer
            self._timer = track_point_in_utc_time(
                self._hass, _interval_update,
                utcnow() + timedelta(seconds=self._usps.interval))

        if self._timer is None:
            self._timer = track_point_in_utc_time(
                self._hass, _interval_update,
                utcnow() + timedelta(seconds=self._usps.interval))

        try:
            return self._mail_img[self._mail_index]
        except IndexError:
            return self._no_mail_img

    @property
    def name(self):
        """Return the name of this camera."""
        try:
            # Include date if available
            return '{} mail {}'.format(self._name, self._usps.mail[0]['date'])
        except IndexError:
            return '{} mail'.format(self._name)
