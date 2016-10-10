"""
Support to check for available updates.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/updater/
"""
import logging
import json
import os
import platform
import uuid
# pylint: disable=no-name-in-module,import-error
from distutils.version import StrictVersion

import requests
import voluptuous as vol

from homeassistant.const import __version__ as CURRENT_VERSION
from homeassistant.const import ATTR_FRIENDLY_NAME
import homeassistant.util.dt as dt_util
from homeassistant.helpers import event
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
UPDATER_URL = 'https://1cnlq5djza.execute-api.us-west-2.amazonaws.com/prod'
DOMAIN = 'updater'
ENTITY_ID = 'updater.updater'
ATTR_RELEASE_NOTES = 'release_notes'
UPDATER_UUID_FILE = '.uuid'
CONF_OPT_OUT = 'opt_out'

REQUIREMENTS = ['distro>=1,<2']

CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    vol.Optional(CONF_OPT_OUT, default=False): cv.boolean
}}, extra=vol.ALLOW_EXTRA)


def _load_uuid(hass, filename=UPDATER_UUID_FILE):
    """Load UUID from a file, if it exist if not create it."""
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        # file not found create it
        with open(path, 'w') as uuidfile:
            uuidfile.write(json.dumps({"uuid": uuid.uuid4().hex}))
            uuidfile.close()

    try:
        with open(path) as uuidfile:
            return uuid.UUID(json.loads(uuidfile.read())['uuid'], version=4)
    except (ValueError, AttributeError):
        return None


def setup(hass, config):
    """Setup the updater component."""
    if 'dev' in CURRENT_VERSION:
        # This component only makes sense in release versions
        _LOGGER.warning('Updater not supported in development version')
        return False

    huuid = _load_uuid(hass).hex

    def check_newest_version(_=None):
        """Check if a new version is available and report if one is."""
        newest, releasenotes = get_newest_version(huuid)

        if newest is not None:
            if StrictVersion(newest) > StrictVersion(CURRENT_VERSION):
                hass.states.set(
                    ENTITY_ID, newest, {ATTR_FRIENDLY_NAME: 'Update Available',
                                        ATTR_RELEASE_NOTES: releasenotes}
                )

    event.track_time_change(
        hass, check_newest_version, hour=[0, 12], minute=0, second=0)

    check_newest_version()

    return True


def get_newest_version(huuid, opt_out=False):
    """Get the newest Home Assistant version."""
    info_object = {'uuid': huuid, 'version': CURRENT_VERSION,
                   'timezone': dt_util.DEFAULT_TIME_ZONE.zone,
                   'os_name': platform.system(), "arch": platform.machine(),
                   'python_version': platform.python_version()}

    if platform.system() == 'Windows':
        info_object['os_version'] = platform.win32_ver()[0]
    elif platform.system() == 'Darwin':
        info_object['os_version'] = platform.mac_ver()[0]
    elif platform.system() == 'Linux':
        import distro
        linux_dist = distro.linux_distribution(full_distribution_name=False)
        info_object['distribution'] = linux_dist[0]
        info_object['os_version'] = linux_dist[1]

    if opt_out:
        info_object = []

    try:
        req = requests.post(UPDATER_URL, json=info_object)
        return (req.json()['version'], req.json()['release-notes'])
    except requests.RequestException:
        _LOGGER.exception('Could not contact HASS Update to check for updates')
        return None
    except ValueError:
        _LOGGER.exception('Received invalid response from HASS Update')
        return None
    except KeyError:
        _LOGGER.exception('Response from HASS Update did not include version')
        return None
