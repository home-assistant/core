"""
components.verisure
~~~~~~~~~~~~~~~~~~~
Provides support for verisure components.

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

REQUIREMENTS = ['vsure==0.6.1']

_LOGGER = logging.getLogger(__name__)

HUB = None


def setup(hass, config):
    """ Setup the Verisure component. """

    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    import verisure
    global HUB
    HUB = VerisureHub(config[DOMAIN], verisure)
    if not HUB.login():
        return False

    # Load components for the devices in the ISY controller that we support
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
    """ Verisure wrapper class """

    MAX_PASSWORD_RETRIES = 2
    MIN_TIME_BETWEEN_REQUESTS = 1

    def __init__(self, domain_config, verisure):
        self.alarm_status = {}
        self.lock_status = {}
        self.climate_status = {}
        self.mouse_status = {}
        self.smartplug_status = {}

        self.config = domain_config
        self._verisure = verisure

        self._lock = threading.Lock()

        self._password_retries = VerisureHub.MAX_PASSWORD_RETRIES
        self._wrong_password_given = False
        self._reconnect_timeout = time.time()

        self.my_pages = verisure.MyPages(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])

    def login(self):
        """ Login to MyPages """
        try:
            self.my_pages.login()
        except self._verisure.Error as ex:
            _LOGGER.error('Could not log in to verisure mypages, %s', ex)
            return False
        return True

    @Throttle(timedelta(seconds=1))
    def update_alarms(self):
        """ Updates the status of the alarm. """
        self.update_component(
            self.my_pages.alarm.get,
            self.alarm_status)

    @Throttle(timedelta(seconds=1))
    def update_locks(self):
        """ Updates the status of the alarm. """
        self.update_component(
            self.my_pages.lock.get,
            self.lock_status)

    @Throttle(timedelta(seconds=60))
    def update_climate(self):
        """ Updates the status of the smartplugs. """
        self.update_component(
            self.my_pages.climate.get,
            self.climate_status)

    @Throttle(timedelta(seconds=60))
    def update_mousedetection(self):
        """ Updates the status of the smartplugs. """
        self.update_component(
            self.my_pages.mousedetection.get,
            self.mouse_status)

    @Throttle(timedelta(seconds=1))
    def update_smartplugs(self):
        """ Updates the status of the smartplugs. """
        self.update_component(
            self.my_pages.smartplug.get,
            self.smartplug_status)

    def update_component(self, get_function, status):
        """ Updates the status of verisure components. """
        if self._wrong_password_given:
            _LOGGER.error('Wrong password for Verisure, update config')
            return
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
        """ Reconnect to verisure mypages. """
        if self._reconnect_timeout > time.time():
            return
        if not self._lock.acquire(blocking=False):
            return
        try:
            self.my_pages.login()
            self._password_retries = VerisureHub.MAX_PASSWORD_RETRIES
        except self._verisure.LoginError as ex:
            _LOGGER.error("Wrong user name or password for Verisure MyPages")
            if self._password_retries > 0:
                self._password_retries -= 1
                self._reconnect_timeout = time.time() + 15 * 60
            else:
                self._wrong_password_given = True
        except self._verisure.MaintenanceError:
            self._reconnect_timeout = time.time() + 60
            _LOGGER.error("Verisure MyPages down for maintenance")
        except self._verisure.Error as ex:
            _LOGGER.error("Could not login to Verisure MyPages, %s", ex)
            self._reconnect_timeout = time.time() + 5
        finally:
            self._lock.release()
