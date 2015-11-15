"""
homeassistant.components.sensor.updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sensor that checks for available updates.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.updater/
"""
import logging

import requests

from homeassistant.const import __version__ as CURRENT_VERSION
from homeassistant.helpers import event

_LOGGER = logging.getLogger(__name__)
PYPI_URL = 'https://pypi.python.org/pypi/homeassistant/json'
DEPENDENCIES = []
DOMAIN = 'updater'


def setup(hass, config):
    ''' setup the updater component '''

    def check_newest_version(_=None):
        ''' check if a new version is available and report if one is '''
        newest = get_newest_version()
        if newest != CURRENT_VERSION and newest is not None:
            hass.states.set(
                '{}.Update'.format(DOMAIN), newest)

    event.track_time_change(hass, check_newest_version,
                            hour=12, minute=0, second=0)
    event.track_time_change(hass, check_newest_version,
                            hour=0, minute=0, second=0)

    check_newest_version()

    return True


def get_newest_version():
    ''' Get the newest HA version form PyPI '''
    try:
        req = requests.get(PYPI_URL)
    except OSError:
        _LOGGER.warning('Could not contact PyPI to check for updates')
        return

    return req.json()['info']['version']
