"""
Support for Verisure components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging
import threading
import time
import os.path
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
import homeassistant.config as conf_util
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['vsure==0.11.1']

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_SERIAL = 'device_serial'

CONF_ALARM = 'alarm'
CONF_CODE_DIGITS = 'code_digits'
CONF_HYDROMETERS = 'hygrometers'
CONF_LOCKS = 'locks'
CONF_MOUSE = 'mouse'
CONF_SMARTPLUGS = 'smartplugs'
CONF_THERMOMETERS = 'thermometers'
CONF_SMARTCAM = 'smartcam'

DOMAIN = 'verisure'

SERVICE_CAPTURE_SMARTCAM = 'capture_smartcam'

HUB = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_ALARM, default=True): cv.boolean,
        vol.Optional(CONF_CODE_DIGITS, default=4): cv.positive_int,
        vol.Optional(CONF_HYDROMETERS, default=True): cv.boolean,
        vol.Optional(CONF_LOCKS, default=True): cv.boolean,
        vol.Optional(CONF_MOUSE, default=True): cv.boolean,
        vol.Optional(CONF_SMARTPLUGS, default=True): cv.boolean,
        vol.Optional(CONF_THERMOMETERS, default=True): cv.boolean,
        vol.Optional(CONF_SMARTCAM, default=True): cv.boolean,
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
    if not HUB.login():
        return False

    for component in ('sensor', 'switch', 'alarm_control_panel', 'lock',
                      'camera'):
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    descriptions = conf_util.load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def capture_smartcam(service):
        """Capture a new picture from a smartcam."""
        device_id = service.data.get(ATTR_DEVICE_SERIAL)
        HUB.smartcam_capture(device_id)
        _LOGGER.debug("Capturing new image from %s", ATTR_DEVICE_SERIAL)

    hass.services.register(DOMAIN, SERVICE_CAPTURE_SMARTCAM,
                           capture_smartcam,
                           descriptions[DOMAIN][SERVICE_CAPTURE_SMARTCAM],
                           schema=CAPTURE_IMAGE_SCHEMA)

    return True


class VerisureHub(object):
    """A Verisure hub wrapper class."""

    def __init__(self, domain_config, verisure):
        """Initialize the Verisure hub."""
        self.alarm_status = {}
        self.lock_status = {}
        self.climate_status = {}
        self.mouse_status = {}
        self.smartplug_status = {}
        self.smartcam_status = {}
        self.smartcam_dict = {}

        self.config = domain_config
        self._verisure = verisure

        self._lock = threading.Lock()

        # When MyPages is brought up from maintenance it sometimes give us a
        # "wrong password" message. We will continue to retry after maintenance
        # regardless of that error.
        self._disable_wrong_password_error = False
        self._password_retries = 1
        self._reconnect_timeout = time.time()

        self.my_pages = verisure.MyPages(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])

    def login(self):
        """Login to Verisure MyPages."""
        try:
            self.my_pages.login()
        except self._verisure.Error as ex:
            _LOGGER.error("Could not log in to verisure mypages, %s", ex)
            return False
        return True

    @Throttle(timedelta(seconds=1))
    def update_alarms(self):
        """Update the status of the alarm."""
        self.update_component(
            self.my_pages.alarm.get,
            self.alarm_status)

    @Throttle(timedelta(seconds=1))
    def update_locks(self):
        """Update the status of the locks."""
        self.update_component(
            self.my_pages.lock.get,
            self.lock_status)

    @Throttle(timedelta(seconds=60))
    def update_climate(self):
        """Update the status of the climate units."""
        self.update_component(
            self.my_pages.climate.get,
            self.climate_status)

    @Throttle(timedelta(seconds=60))
    def update_mousedetection(self):
        """Update the status of the mouse detectors."""
        self.update_component(
            self.my_pages.mousedetection.get,
            self.mouse_status)

    @Throttle(timedelta(seconds=1))
    def update_smartplugs(self):
        """Update the status of the smartplugs."""
        self.update_component(
            self.my_pages.smartplug.get,
            self.smartplug_status)

    @Throttle(timedelta(seconds=30))
    def update_smartcam(self):
        """Update the status of the smartcam."""
        self.update_component(
            self.my_pages.smartcam.get,
            self.smartcam_status)

    @Throttle(timedelta(seconds=30))
    def update_smartcam_imagelist(self):
        """Update the imagelist for the camera."""
        _LOGGER.debug("Running update imagelist")
        self.smartcam_dict = self.my_pages.smartcam.get_imagelist()
        _LOGGER.debug("New dict: %s", self.smartcam_dict)

    @Throttle(timedelta(seconds=30))
    def smartcam_capture(self, device_id):
        """Capture a new image from a smartcam."""
        self.my_pages.smartcam.capture(device_id)

    @property
    def available(self):
        """Return True if hub is available."""
        return self._password_retries >= 0

    def update_component(self, get_function, status):
        """Update the status of Verisure components."""
        try:
            for overview in get_function():
                try:
                    status[overview.id] = overview
                except AttributeError:
                    status[overview.deviceLabel] = overview
        except self._verisure.Error as ex:
            _LOGGER.info("Caught connection error %s, tries to reconnect", ex)
            self.reconnect()

    def reconnect(self):
        """Reconnect to Verisure MyPages."""
        if (self._reconnect_timeout > time.time() or
                not self._lock.acquire(blocking=False) or
                self._password_retries < 0):
            return
        try:
            self.my_pages.login()
            self._disable_wrong_password_error = False
            self._password_retries = 1
        except self._verisure.LoginError as ex:
            _LOGGER.error("Wrong user name or password for Verisure MyPages")
            if self._disable_wrong_password_error:
                self._reconnect_timeout = time.time() + 60*60
            else:
                self._password_retries = self._password_retries - 1
        except self._verisure.MaintenanceError:
            self._disable_wrong_password_error = True
            self._reconnect_timeout = time.time() + 60*60
            _LOGGER.error("Verisure MyPages down for maintenance")
        except self._verisure.Error as ex:
            _LOGGER.error("Could not login to Verisure MyPages, %s", ex)
            self._reconnect_timeout = time.time() + 60
        finally:
            self._lock.release()
