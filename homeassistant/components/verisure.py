"""
Support for Verisure components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging
import threading
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['vsure==1.5.0', 'jsonpath==0.75']

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_SERIAL = 'device_serial'

CONF_ALARM = 'alarm'
CONF_CODE_DIGITS = 'code_digits'
CONF_DOOR_WINDOW = 'door_window'
CONF_GIID = 'giid'
CONF_HYDROMETERS = 'hygrometers'
CONF_LOCKS = 'locks'
CONF_MOUSE = 'mouse'
CONF_SMARTPLUGS = 'smartplugs'
CONF_THERMOMETERS = 'thermometers'
CONF_SMARTCAM = 'smartcam'

DOMAIN = 'verisure'

MIN_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

SERVICE_CAPTURE_SMARTCAM = 'capture_smartcam'

HUB = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_ALARM, default=True): cv.boolean,
        vol.Optional(CONF_CODE_DIGITS, default=4): cv.positive_int,
        vol.Optional(CONF_DOOR_WINDOW, default=True): cv.boolean,
        vol.Optional(CONF_GIID): cv.string,
        vol.Optional(CONF_HYDROMETERS, default=True): cv.boolean,
        vol.Optional(CONF_LOCKS, default=True): cv.boolean,
        vol.Optional(CONF_MOUSE, default=True): cv.boolean,
        vol.Optional(CONF_SMARTPLUGS, default=True): cv.boolean,
        vol.Optional(CONF_THERMOMETERS, default=True): cv.boolean,
        vol.Optional(CONF_SMARTCAM, default=True): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))),
    }),
}, extra=vol.ALLOW_EXTRA)

CAPTURE_IMAGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_SERIAL): cv.string
})


def setup(hass, config):
    """Set up the Verisure component."""
    import verisure
    global HUB
    HUB = VerisureHub(config[DOMAIN], verisure)
    HUB.update_overview = Throttle(
        config[DOMAIN][CONF_SCAN_INTERVAL])(HUB.update_overview)
    if not HUB.login():
        return False
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: HUB.logout())
    HUB.update_overview()

    for component in ('sensor', 'switch', 'alarm_control_panel', 'lock',
                      'camera', 'binary_sensor'):
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    def capture_smartcam(service):
        """Capture a new picture from a smartcam."""
        device_id = service.data.get(ATTR_DEVICE_SERIAL)
        HUB.smartcam_capture(device_id)
        _LOGGER.debug("Capturing new image from %s", ATTR_DEVICE_SERIAL)

    hass.services.register(DOMAIN, SERVICE_CAPTURE_SMARTCAM,
                           capture_smartcam,
                           schema=CAPTURE_IMAGE_SCHEMA)

    return True


class VerisureHub:
    """A Verisure hub wrapper class."""

    def __init__(self, domain_config, verisure):
        """Initialize the Verisure hub."""
        self.overview = {}
        self.imageseries = {}

        self.config = domain_config
        self._verisure = verisure

        self._lock = threading.Lock()

        self.session = verisure.Session(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])

        self.giid = domain_config.get(CONF_GIID)

        import jsonpath
        self.jsonpath = jsonpath.jsonpath

    def login(self):
        """Login to Verisure."""
        try:
            self.session.login()
        except self._verisure.Error as ex:
            _LOGGER.error('Could not log in to verisure, %s', ex)
            return False
        if self.giid:
            return self.set_giid()
        return True

    def logout(self):
        """Logout from Verisure."""
        try:
            self.session.logout()
        except self._verisure.Error as ex:
            _LOGGER.error('Could not log out from verisure, %s', ex)
            return False
        return True

    def set_giid(self):
        """Set installation GIID."""
        try:
            self.session.set_giid(self.giid)
        except self._verisure.Error as ex:
            _LOGGER.error('Could not set installation GIID, %s', ex)
            return False
        return True

    def update_overview(self):
        """Update the overview."""
        try:
            self.overview = self.session.get_overview()
        except self._verisure.ResponseError as ex:
            _LOGGER.error('Could not read overview, %s', ex)
            if ex.status_code == 503:  # Service unavailable
                _LOGGER.info('Trying to log in again')
                self.login()
            else:
                raise

    @Throttle(timedelta(seconds=60))
    def update_smartcam_imageseries(self):
        """Update the image series."""
        self.imageseries = self.session.get_camera_imageseries()

    @Throttle(timedelta(seconds=30))
    def smartcam_capture(self, device_id):
        """Capture a new image from a smartcam."""
        self.session.capture_image(device_id)

    def get(self, jpath, *args):
        """Get values from the overview that matches the jsonpath."""
        res = self.jsonpath(self.overview, jpath % args)
        return res if res else []

    def get_first(self, jpath, *args):
        """Get first value from the overview that matches the jsonpath."""
        res = self.get(jpath, *args)
        return res[0] if res else None

    def get_image_info(self, jpath, *args):
        """Get values from the imageseries that matches the jsonpath."""
        res = self.jsonpath(self.imageseries, jpath % args)
        return res if res else []
