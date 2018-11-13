"""
Sensor that can display the current Home Assistant versions.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.version/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_SOURCE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyhaversion==2.0.3']

_LOGGER = logging.getLogger(__name__)

ALL_IMAGES = [
    'default', 'intel-nuc', 'qemux86', 'qemux86-64', 'qemuarm',
    'qemuarm-64', 'raspberrypi', 'raspberrypi2', 'raspberrypi3',
    'raspberrypi3-64', 'tinker', 'odroid-c2', 'odroid-xu'
]
ALL_SOURCES = [
    'local', 'pypi', 'hassio', 'docker'
]

CONF_BETA = 'beta'
CONF_IMAGE = 'image'

DEFAULT_IMAGE = 'default'
DEFAULT_NAME_LATEST = "Latest Version"
DEFAULT_NAME_LOCAL = "Current Version"
DEFAULT_SOURCE = 'local'

ICON = 'mdi:package-up'

TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BETA, default=False): cv.boolean,
    vol.Optional(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(ALL_IMAGES),
    vol.Optional(CONF_NAME, default=''): cv.string,
    vol.Optional(CONF_SOURCE, default=DEFAULT_SOURCE): vol.In(ALL_SOURCES),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Version sensor platform."""
    from pyhaversion import Version
    beta = config.get(CONF_BETA)
    image = config.get(CONF_IMAGE)
    name = config.get(CONF_NAME)
    source = config.get(CONF_SOURCE)

    session = async_get_clientsession(hass)
    if beta:
        branch = 'beta'
    else:
        branch = 'stable'
    haversion = VersionData(Version(hass.loop, session, branch, image), source)

    async_add_entities([VersionSensor(haversion, name)], True)


class VersionSensor(Entity):
    """Representation of a Home Assistant version sensor."""

    def __init__(self, haversion, name=''):
        """Initialize the Version sensor."""
        self.haversion = haversion
        self._name = name
        self._state = None

    async def async_update(self):
        """Get the latest version information."""
        await self.haversion.async_update()

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._name:
            return self._name
        if self.haversion.source == DEFAULT_SOURCE:
            return DEFAULT_NAME_LOCAL
        return DEFAULT_NAME_LATEST

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.haversion.api.version

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self.haversion.api.version_data

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON


class VersionData:
    """Get the latest data and update the states."""

    def __init__(self, api, source):
        """Initialize the data object."""
        self.api = api
        self.source = source

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest version information."""
        if self.source == 'pypi':
            await self.api.get_pypi_version()
        elif self.source == 'hassio':
            await self.api.get_hassio_version()
        elif self.source == 'docker':
            await self.api.get_docker_version()
        else:
            await self.api.get_local_version()
