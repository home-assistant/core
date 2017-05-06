"""
Support to check for available updates.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/updater/
"""
import asyncio
import json
import logging
import os
import platform
import uuid
from datetime import timedelta
# pylint: disable=no-name-in-module, import-error
from distutils.version import StrictVersion

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, __version__ as CURRENT_VERSION)
from homeassistant.helpers import event

REQUIREMENTS = ['distro==1.0.4']

_LOGGER = logging.getLogger(__name__)

ATTR_RELEASE_NOTES = 'release_notes'

CONF_REPORTING = 'reporting'

DOMAIN = 'updater'

ENTITY_ID = 'updater.updater'

UPDATER_URL = 'https://updater.home-assistant.io/'
UPDATER_UUID_FILE = '.uuid'

CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    vol.Optional(CONF_REPORTING, default=True): cv.boolean
}}, extra=vol.ALLOW_EXTRA)

RESPONSE_SCHEMA = vol.Schema({
    vol.Required('version'): str,
    vol.Required('release-notes'): cv.url,
})


def _create_uuid(hass, filename=UPDATER_UUID_FILE):
    """Create UUID and save it in a file."""
    with open(hass.config.path(filename), 'w') as fptr:
        _uuid = uuid.uuid4().hex
        fptr.write(json.dumps({'uuid': _uuid}))
        return _uuid


def _load_uuid(hass, filename=UPDATER_UUID_FILE):
    """Load UUID from a file or return None."""
    try:
        with open(hass.config.path(filename)) as fptr:
            jsonf = json.loads(fptr.read())
            return uuid.UUID(jsonf['uuid'], version=4).hex
    except (ValueError, AttributeError):
        return None
    except FileNotFoundError:
        return _create_uuid(hass, filename)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the updater component."""
    if 'dev' in CURRENT_VERSION:
        # This component only makes sense in release versions
        _LOGGER.warning("Running on 'dev', only analytics will be submitted")

    config = config.get(DOMAIN, {})
    if config.get(CONF_REPORTING):
        huuid = yield from hass.async_add_job(_load_uuid, hass)
    else:
        huuid = None

    @asyncio.coroutine
    def check_new_version(now):
        """Check if a new version is available and report if one is."""
        result = yield from get_newest_version(hass, huuid)

        if result is None:
            return

        newest, releasenotes = result

        if newest is None or 'dev' in CURRENT_VERSION:
            return

        if StrictVersion(newest) > StrictVersion(CURRENT_VERSION):
            _LOGGER.info("The latest available version is %s", newest)
            hass.states.async_set(
                ENTITY_ID, newest, {ATTR_FRIENDLY_NAME: 'Update Available',
                                    ATTR_RELEASE_NOTES: releasenotes}
            )
        elif StrictVersion(newest) == StrictVersion(CURRENT_VERSION):
            _LOGGER.info(
                "You are on the latest version (%s) of Home Assistant", newest)

    # Update daily, start 1 hour after startup
    _dt = dt_util.utcnow() + timedelta(hours=1)
    event.async_track_utc_time_change(
        hass, check_new_version,
        hour=_dt.hour, minute=_dt.minute, second=_dt.second)

    return True


@asyncio.coroutine
def get_system_info(hass):
    """Return info about the system."""
    info_object = {
        'arch': platform.machine(),
        'dev': 'dev' in CURRENT_VERSION,
        'docker': False,
        'os_name': platform.system(),
        'python_version': platform.python_version(),
        'timezone': dt_util.DEFAULT_TIME_ZONE.zone,
        'version': CURRENT_VERSION,
        'virtualenv': os.environ.get('VIRTUAL_ENV') is not None,
    }

    if platform.system() == 'Windows':
        info_object['os_version'] = platform.win32_ver()[0]
    elif platform.system() == 'Darwin':
        info_object['os_version'] = platform.mac_ver()[0]
    elif platform.system() == 'FreeBSD':
        info_object['os_version'] = platform.release()
    elif platform.system() == 'Linux':
        import distro
        linux_dist = yield from hass.async_add_job(
            distro.linux_distribution, False)
        info_object['distribution'] = linux_dist[0]
        info_object['os_version'] = linux_dist[1]
        info_object['docker'] = os.path.isfile('/.dockerenv')

    return info_object


@asyncio.coroutine
def get_newest_version(hass, huuid):
    """Get the newest Home Assistant version."""
    if huuid:
        info_object = yield from get_system_info(hass)
        info_object['huuid'] = huuid
    else:
        info_object = {}

    session = async_get_clientsession(hass)
    try:
        with async_timeout.timeout(5, loop=hass.loop):
            req = yield from session.post(UPDATER_URL, json=info_object)
        _LOGGER.info(("Submitted analytics to Home Assistant servers. "
                      "Information submitted includes %s"), info_object)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not contact Home Assistant Update to check "
                      "for updates")
        return None

    try:
        res = yield from req.json()
    except ValueError:
        _LOGGER.error("Received invalid JSON from Home Assistant Update")
        return None

    try:
        res = RESPONSE_SCHEMA(res)
        return (res['version'], res['release-notes'])
    except vol.Invalid:
        _LOGGER.error('Got unexpected response: %s', res)
        return None
