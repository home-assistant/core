"""
Support to check for available updates.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/updater/
"""
from datetime import datetime, timedelta
import logging
import json
import platform
import uuid
import os
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
UPDATER_URL = 'https://updater.home-assistant.io/'
DOMAIN = 'updater'
ENTITY_ID = 'updater.updater'
ATTR_RELEASE_NOTES = 'release_notes'
UPDATER_UUID_FILE = '.uuid'
CONF_REPORTING = 'reporting'

REQUIREMENTS = ['distro==1.0.0']

CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    vol.Optional(CONF_REPORTING, default=True): cv.boolean
}}, extra=vol.ALLOW_EXTRA)


def _create_uuid(hass, filename=UPDATER_UUID_FILE):
    """Create UUID and save it in a file."""
    with open(hass.config.path(filename), 'w') as fptr:
        _uuid = uuid.uuid4().hex
        fptr.write(json.dumps({"uuid": _uuid}))
        return _uuid


def _load_uuid(hass, filename=UPDATER_UUID_FILE):
    """Load UUID from a file, or return None."""
    try:
        with open(hass.config.path(filename)) as fptr:
            jsonf = json.loads(fptr.read())
            return uuid.UUID(jsonf['uuid'], version=4).hex
    except (ValueError, AttributeError):
        return None
    except FileNotFoundError:
        return _create_uuid(hass, filename)


def setup(hass, config):
    """Setup the updater component."""
    if 'dev' in CURRENT_VERSION:
        # This component only makes sense in release versions
        _LOGGER.warning('Updater not supported in development version')
        return False

    config = config.get(DOMAIN, {})
    huuid = _load_uuid(hass) if config.get(CONF_REPORTING) else None

    # Update daily, start 1 hour after startup
    _dt = datetime.now() + timedelta(hours=1)
    event.track_time_change(
        hass, lambda _: check_newest_version(hass, huuid),
        hour=_dt.hour, minute=_dt.minute, second=_dt.second)

    return True


def check_newest_version(hass, huuid):
    """Check if a new version is available and report if one is."""
    newest, releasenotes = get_newest_version(huuid)

    if newest is not None:
        if StrictVersion(newest) > StrictVersion(CURRENT_VERSION):
            hass.states.set(
                ENTITY_ID, newest, {ATTR_FRIENDLY_NAME: 'Update Available',
                                    ATTR_RELEASE_NOTES: releasenotes}
            )


def get_newest_version(huuid):
    """Get the newest Home Assistant version."""
    info_object = {'uuid': huuid, 'version': CURRENT_VERSION,
                   'timezone': dt_util.DEFAULT_TIME_ZONE.zone,
                   'os_name': platform.system(), "arch": platform.machine(),
                   'python_version': platform.python_version(),
                   'virtualenv': (os.environ.get('VIRTUAL_ENV') is not None),
                   'docker': False}

    if platform.system() == 'Windows':
        info_object['os_version'] = platform.win32_ver()[0]
    elif platform.system() == 'Darwin':
        info_object['os_version'] = platform.mac_ver()[0]
    elif platform.system() == 'Linux':
        import distro
        linux_dist = distro.linux_distribution(full_distribution_name=False)
        info_object['distribution'] = linux_dist[0]
        info_object['os_version'] = linux_dist[1]
        info_object['docker'] = os.path.isfile('/.dockerenv')

    if not huuid:
        info_object = {}

    try:
        req = requests.post(UPDATER_URL, json=info_object)
        res = req.json()
        _LOGGER.info(('The latest version is %s. '
                      'Information submitted includes %s'),
                     res['version'], info_object)
        return (res['version'], res['release-notes'])
    except requests.RequestException:
        _LOGGER.exception('Could not contact HASS Update to check for updates')
        return None
    except ValueError:
        _LOGGER.exception('Received invalid response from HASS Update')
        return None
    except KeyError:
        _LOGGER.exception('Response from HASS Update did not include version')
        return None
