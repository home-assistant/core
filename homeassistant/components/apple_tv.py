"""
Support for Apple TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/apple_tv/
"""
import asyncio

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import discovery
from homeassistant.components.discovery import SERVICE_APPLE_TV
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['pyatv==0.3.2']

DOMAIN = 'apple_tv'

ATTR_ATV = 'atv'
ATTR_POWER = 'power'

CONF_LOGIN_ID = 'login_id'
CONF_START_OFF = 'start_off'
CONF_CREDENTIALS = 'credentials'

DEFAULT_NAME = 'Apple TV'

DATA_APPLE_TV = 'data_apple_tv'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_LOGIN_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CREDENTIALS, default=None): cv.string,
        vol.Optional(CONF_START_OFF, default=False): cv.boolean
    })])
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Apple TV component."""
    if DATA_APPLE_TV not in hass.data:
        hass.data[DATA_APPLE_TV] = {}

    @asyncio.coroutine
    def atv_discovered(service, info):
        """Setup an Apple TV that was auto discovered."""
        yield from _setup_atv(hass, {
            CONF_NAME: info['name'],
            CONF_HOST: info['host'],
            CONF_LOGIN_ID: info['properties']['hG'],
            CONF_START_OFF: False
        })

    discovery.async_listen(hass, SERVICE_APPLE_TV, atv_discovered)

    tasks = [_setup_atv(hass, conf) for conf in config.get(DOMAIN, [])]
    if tasks:
        yield from asyncio.wait(tasks, loop=hass.loop)

    return True


@asyncio.coroutine
def _setup_atv(hass, atv_config):
    """Setup an Apple TV."""
    import pyatv
    name = atv_config.get(CONF_NAME)
    host = atv_config.get(CONF_HOST)
    login_id = atv_config.get(CONF_LOGIN_ID)
    start_off = atv_config.get(CONF_START_OFF)
    credentials = atv_config.get(CONF_CREDENTIALS)

    if host in hass.data[DATA_APPLE_TV]:
        return

    details = pyatv.AppleTVDevice(name, host, login_id)
    session = async_get_clientsession(hass)
    atv = pyatv.connect_to_apple_tv(details, hass.loop, session=session)
    if credentials:
        yield from atv.airplay.load_credentials(credentials)

    power = AppleTVPowerManager(hass, atv, start_off)
    hass.data[DATA_APPLE_TV][host] = {
        ATTR_ATV: atv,
        ATTR_POWER: power
    }

    hass.async_add_job(discovery.async_load_platform(
        hass, 'media_player', DOMAIN, atv_config))

    hass.async_add_job(discovery.async_load_platform(
        hass, 'remote', DOMAIN, atv_config))


class AppleTVPowerManager:
    """Manager for global power management of an Apple TV.

    An instance is used per device to share the same power state between
    several platforms.
    """

    def __init__(self, hass, atv, is_off):
        """Initialize power manager."""
        self.hass = hass
        self.atv = atv
        self.listeners = []
        self._is_on = not is_off

    def init(self):
        """Initialize power management."""
        if self._is_on:
            self.atv.push_updater.start()

    @property
    def turned_on(self):
        """If device is on or off."""
        return self._is_on

    def set_power_on(self, value):
        """Change if a device is on or off."""
        if value != self._is_on:
            self._is_on = value
            if not self._is_on:
                self.atv.push_updater.stop()
            else:
                self.atv.push_updater.start()

            for listener in self.listeners:
                self.hass.async_add_job(listener.async_update_ha_state())
