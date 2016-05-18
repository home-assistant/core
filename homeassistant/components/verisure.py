"""
Support for Verisure components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging
import threading
import time
from datetime import timedelta

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, CONF_PASSWORD, CONF_USERNAME,
    EVENT_PLATFORM_DISCOVERED)
from homeassistant.helpers import validate_config
from homeassistant.loader import get_component
from homeassistant.util import Throttle

DOMAIN = "verisure"
DISCOVER_SENSORS = 'verisure.sensors'
DISCOVER_SWITCHES = 'verisure.switches'
DISCOVER_ALARMS = 'verisure.alarm_control_panel'
DISCOVER_LOCKS = 'verisure.lock'

REQUIREMENTS = ['vsure==0.8.1']

_LOGGER = logging.getLogger(__name__)

HUB = None


def setup(hass, config):
    """Setup the Verisure component."""
    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    import verisure
    global HUB
    HUB = VerisureHub(config[DOMAIN], verisure)
    if not HUB.login():
        return False

    for comp_name, discovery in ((('sensor', DISCOVER_SENSORS),
                                  ('switch', DISCOVER_SWITCHES),
                                  ('alarm_control_panel', DISCOVER_ALARMS),
                                  ('lock', DISCOVER_LOCKS))):
        component = get_component(comp_name)
        bootstrap.setup_component(hass, component.DOMAIN, config)
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: discovery,
                       ATTR_DISCOVERED: {}})

    return True


# pylint: disable=too-many-instance-attributes
class VerisureHub(object):
    """A Verisure hub wrapper class."""

    def __init__(self, domain_config, verisure):
        """Initialize the Verisure hub."""
        self.alarm_status = {}
        self.lock_status = {}
        self.climate_status = {}
        self.mouse_status = {}
        self.smartplug_status = {}

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
            _LOGGER.error('Could not log in to verisure mypages, %s', ex)
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
            _LOGGER.error('Caught connection error %s, tries to reconnect', ex)
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
