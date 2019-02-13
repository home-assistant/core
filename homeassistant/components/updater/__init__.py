"""Support to check for available updates."""
import asyncio
from datetime import timedelta
# pylint: disable=import-error,no-name-in-module
from distutils.version import StrictVersion
import json
import logging
import uuid

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME, __version__ as current_version)
from homeassistant.helpers import event
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['distro==1.4.0']

_LOGGER = logging.getLogger(__name__)

ATTR_RELEASE_NOTES = 'release_notes'

CONF_REPORTING = 'reporting'
CONF_COMPONENT_REPORTING = 'include_used_components'

DOMAIN = 'updater'

ENTITY_ID = 'updater.updater'

UPDATER_URL = 'https://updater.home-assistant.io/'
UPDATER_UUID_FILE = '.uuid'

CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    vol.Optional(CONF_REPORTING, default=True): cv.boolean,
    vol.Optional(CONF_COMPONENT_REPORTING, default=False): cv.boolean,
}}, extra=vol.ALLOW_EXTRA)

RESPONSE_SCHEMA = vol.Schema({
    vol.Required('version'): cv.string,
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


async def async_setup(hass, config):
    """Set up the updater component."""
    if 'dev' in current_version:
        # This component only makes sense in release versions
        _LOGGER.info("Running on 'dev', only analytics will be submitted")

    config = config.get(DOMAIN, {})
    if config.get(CONF_REPORTING):
        huuid = await hass.async_add_job(_load_uuid, hass)
    else:
        huuid = None

    include_components = config.get(CONF_COMPONENT_REPORTING)

    async def check_new_version(now):
        """Check if a new version is available and report if one is."""
        result = await get_newest_version(hass, huuid, include_components)

        if result is None:
            return

        newest, releasenotes = result

        # Skip on dev
        if newest is None or 'dev' in current_version:
            return

        # Load data from supervisor on hass.io
        if hass.components.hassio.is_hassio():
            newest = hass.components.hassio.get_homeassistant_version()

        # Validate version
        if StrictVersion(newest) > StrictVersion(current_version):
            _LOGGER.info("The latest available version is %s", newest)
            hass.states.async_set(
                ENTITY_ID, newest, {ATTR_FRIENDLY_NAME: 'Update Available',
                                    ATTR_RELEASE_NOTES: releasenotes}
            )
        elif StrictVersion(newest) == StrictVersion(current_version):
            _LOGGER.info(
                "You are on the latest version (%s) of Home Assistant", newest)

    # Update daily, start 1 hour after startup
    _dt = dt_util.utcnow() + timedelta(hours=1)
    event.async_track_utc_time_change(
        hass, check_new_version,
        hour=_dt.hour, minute=_dt.minute, second=_dt.second)

    return True


async def get_newest_version(hass, huuid, include_components):
    """Get the newest Home Assistant version."""
    if huuid:
        info_object = \
            await hass.helpers.system_info.async_get_system_info()

        if include_components:
            info_object['components'] = list(hass.config.components)

        import distro

        linux_dist = await hass.async_add_executor_job(
            distro.linux_distribution, False)
        info_object['distribution'] = linux_dist[0]
        info_object['os_version'] = linux_dist[1]

        info_object['huuid'] = huuid
    else:
        info_object = {}

    session = async_get_clientsession(hass)
    try:
        with async_timeout.timeout(5, loop=hass.loop):
            req = await session.post(UPDATER_URL, json=info_object)
        _LOGGER.info(("Submitted analytics to Home Assistant servers. "
                      "Information submitted includes %s"), info_object)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not contact Home Assistant Update to check "
                      "for updates")
        return None

    try:
        res = await req.json()
    except ValueError:
        _LOGGER.error("Received invalid JSON from Home Assistant Update")
        return None

    try:
        res = RESPONSE_SCHEMA(res)
        return res['version'], res['release-notes']
    except vol.Invalid:
        _LOGGER.error("Got unexpected response: %s", res)
        return None
