"""
components.verisure
~~~~~~~~~~~~~~~~~~
"""
import logging
from datetime import timedelta

from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    CONF_USERNAME, CONF_PASSWORD)

DOMAIN = "verisure"
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/persandstrom/python-verisure/archive/master.zip'
    ]

_LOGGER = logging.getLogger(__name__)

MY_PAGES = None
STATUS = {}

MIN_TIME_BETWEEN_REQUESTS = timedelta(seconds=5)


def setup(hass, config):
    """ Setup the Verisure component. """

    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    from verisure import MyPages

    STATUS[MyPages.DEVICE_ALARM] = {}
    STATUS[MyPages.DEVICE_CLIMATE] = {}
    STATUS[MyPages.DEVICE_SMARTPLUG] = {}

    global MY_PAGES
    MY_PAGES = MyPages(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD])
    MY_PAGES.login()
    update()

    def stop_verisure(event):
        """ Stop the Verisure service. """
        MY_PAGES.logout()

    def start_verisure(event):
        """ Start the Verisure service. """
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_verisure)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_verisure)

    return True


def get_alarm_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_ALARM]


def get_climate_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_CLIMATE]


def get_smartplug_status():
    ''' return a list of status overviews for alarm components '''
    return STATUS[MY_PAGES.DEVICE_SMARTPLUG]


@Throttle(MIN_TIME_BETWEEN_REQUESTS)
def update():
    ''' Updates the status of verisure components '''
    try:
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_ALARM):
            STATUS[MY_PAGES.DEVICE_ALARM][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_CLIMATE):
            STATUS[MY_PAGES.DEVICE_CLIMATE][overview.id] = overview
        for overview in MY_PAGES.get_overview(MY_PAGES.DEVICE_SMARTPLUG):
            STATUS[MY_PAGES.DEVICE_SMARTPLUG][overview.id] = overview
    except ConnectionError as ex:
        _LOGGER.error('Caught connection error %s, tries to reconnect', ex)
        MY_PAGES.login()
