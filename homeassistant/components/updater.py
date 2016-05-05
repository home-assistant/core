"""
Support to check for available updates.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/updater/
"""
import logging

import requests

from homeassistant.const import __version__ as CURRENT_VERSION
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers import event

_LOGGER = logging.getLogger(__name__)
PYPI_URL = 'https://pypi.python.org/pypi/homeassistant/json'
DOMAIN = 'updater'
ENTITY_ID = 'updater.updater'


def setup(hass, config):
    """Setup the updater component."""
    if 'dev' in CURRENT_VERSION:
        # This component only makes sense in release versions
        _LOGGER.warning('Updater not supported in development version')
        return False

    def check_newest_version(_=None):
        """Check if a new version is available and report if one is."""
        newest = get_newest_version()

        if newest != CURRENT_VERSION and newest is not None:
            hass.states.set(
                ENTITY_ID, newest, {ATTR_FRIENDLY_NAME: 'Update Available'})

    event.track_time_change(hass, check_newest_version,
                            hour=[0, 12], minute=0, second=0)

    check_newest_version()

    return True


def get_newest_version():
    """Get the newest Home Assistant version from PyPI."""
    try:
        req = requests.get(PYPI_URL)

        return req.json()['info']['version']
    except requests.RequestException:
        _LOGGER.exception('Could not contact PyPI to check for updates')
        return None
    except ValueError:
        _LOGGER.exception('Received invalid response from PyPI')
        return None
    except KeyError:
        _LOGGER.exception('Response from PyPI did not include version')
        return None
