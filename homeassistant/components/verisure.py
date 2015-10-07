"""
components.verisure
~~~~~~~~~~~~~~~~~~~
Provides support for verisure components.

Configuration:

To use the Verisure component you will need to add something like the
following to your configuration.yaml file.

verisure:
  username: user@example.com
  password: password
  alarm: 1
  hygrometers: 0
  smartplugs: 1
  thermometers: 0

Variables:

username
*Required
Username to Verisure mypages.

password
*Required
Password to Verisure mypages.

alarm
*Optional
Set to 1 to show alarm, 0 to disable. Default 1.

hygrometers
*Optional
Set to 1 to show hygrometers, 0 to disable. Default 1.

smartplugs
*Optional
Set to 1 to show smartplugs, 0 to disable. Default 1.

thermometers
*Optional
Set to 1 to show thermometers, 0 to disable. Default 1.
"""
import logging
from datetime import timedelta

from homeassistant import bootstrap
from homeassistant.loader import get_component

from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED,
    CONF_USERNAME, CONF_PASSWORD)


DOMAIN = "verisure"
DISCOVER_SENSORS = 'verisure.sensors'
DISCOVER_SWITCHES = 'verisure.switches'
DISCOVER_ALARMS = 'verisure.alarm_control_panel'

DEPENDENCIES = ['alarm_control_panel']
REQUIREMENTS = [
    'https://github.com/persandstrom/python-verisure/archive/'
    '9873c4527f01b1ba1f72ae60f7f35854390d59be.zip#python-verisure==0.2.6'
]

_LOGGER = logging.getLogger(__name__)

MY_PAGES = None
STATUS = {}

VERISURE_LOGIN_ERROR = None
VERISURE_ERROR = None

SHOW_THERMOMETERS = True
SHOW_HYGROMETERS = True
SHOW_ALARM = True
SHOW_SMARTPLUGS = True

# if wrong password was given don't try again
WRONG_PASSWORD_GIVEN = False

MIN_TIME_BETWEEN_REQUESTS = timedelta(seconds=5)


def setup(hass, config):
    """ Setup the Verisure component. """

    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    from verisure import MyPages, LoginError, Error

    STATUS[MyPages.DEVICE_ALARM] = {}
    STATUS[MyPages.DEVICE_CLIMATE] = {}
    STATUS[MyPages.DEVICE_SMARTPLUG] = {}

    global SHOW_THERMOMETERS, SHOW_HYGROMETERS, SHOW_ALARM, SHOW_SMARTPLUGS
    SHOW_THERMOMETERS = int(config[DOMAIN].get('thermometers', '1'))
    SHOW_HYGROMETERS = int(config[DOMAIN].get('hygrometers', '1'))
    SHOW_ALARM = int(config[DOMAIN].get('alarm', '1'))
    SHOW_SMARTPLUGS = int(config[DOMAIN].get('smartplugs', '1'))

    global MY_PAGES
    MY_PAGES = MyPages(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD])
    global VERISURE_LOGIN_ERROR, VERISURE_ERROR
    VERISURE_LOGIN_ERROR = LoginError
    VERISURE_ERROR = Error

    try:
        MY_PAGES.login()
    except (ConnectionError, Error) as ex:
        _LOGGER.error('Could not log in to verisure mypages, %s', ex)
        return False

    update()

    # Load components for the devices in the ISY controller that we support
    for comp_name, discovery in ((('sensor', DISCOVER_SENSORS),
                                  ('switch', DISCOVER_SWITCHES),
                                  ('alarm_control_panel', DISCOVER_ALARMS))):
        component = get_component(comp_name)
        _LOGGER.info(config[DOMAIN])
        bootstrap.setup_component(hass, component.DOMAIN, config)

        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: discovery,
                       ATTR_DISCOVERED: {}})

    return True


def get_alarm_status():
    """ Return a list of status overviews for alarm components. """
    return STATUS[MY_PAGES.DEVICE_ALARM]


def get_climate_status():
    """ Return a list of status overviews for alarm components. """
    return STATUS[MY_PAGES.DEVICE_CLIMATE]


def get_smartplug_status():
    """ Return a list of status overviews for alarm components. """
    return STATUS[MY_PAGES.DEVICE_SMARTPLUG]


def reconnect():
    """ Reconnect to verisure mypages. """
    try:
        MY_PAGES.login()
    except VERISURE_LOGIN_ERROR as ex:
        _LOGGER.error("Could not login to Verisure mypages, %s", ex)
        global WRONG_PASSWORD_GIVEN
        WRONG_PASSWORD_GIVEN = True
    except (ConnectionError, VERISURE_ERROR) as ex:
        _LOGGER.error("Could not login to Verisure mypages, %s", ex)


@Throttle(MIN_TIME_BETWEEN_REQUESTS)
def update():
    """ Updates the status of verisure components. """
    if WRONG_PASSWORD_GIVEN:
        _LOGGER.error('Wrong password')
        return

    try:
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_ALARM):
            STATUS[MY_PAGES.DEVICE_ALARM][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_CLIMATE):
            STATUS[MY_PAGES.DEVICE_CLIMATE][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_SMARTPLUG):
            STATUS[MY_PAGES.DEVICE_SMARTPLUG][overview.id] = overview
    except ConnectionError as ex:
        _LOGGER.error('Caught connection error %s, tries to reconnect', ex)
        reconnect()
