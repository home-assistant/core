"""
Support for Apple TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/apple_tv/
"""
import asyncio
import logging

from typing import Sequence, TypeVar, Union

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_APPLE_TV
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyatv==0.3.10']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'apple_tv'

SERVICE_SCAN = 'apple_tv_scan'
SERVICE_AUTHENTICATE = 'apple_tv_authenticate'

ATTR_ATV = 'atv'
ATTR_POWER = 'power'

CONF_LOGIN_ID = 'login_id'
CONF_START_OFF = 'start_off'
CONF_CREDENTIALS = 'credentials'

DEFAULT_NAME = 'Apple TV'

DATA_APPLE_TV = 'data_apple_tv'
DATA_ENTITIES = 'data_apple_tv_entities'

KEY_CONFIG = 'apple_tv_configuring'

NOTIFICATION_AUTH_ID = 'apple_tv_auth_notification'
NOTIFICATION_AUTH_TITLE = 'Apple TV Authentication'
NOTIFICATION_SCAN_ID = 'apple_tv_scan_notification'
NOTIFICATION_SCAN_TITLE = 'Apple TV Scan'

T = TypeVar('T')  # pylint: disable=invalid-name


# This version of ensure_list interprets an empty dict as no value
def ensure_list(value: Union[T, Sequence[T]]) -> Sequence[T]:
    """Wrap value in list if it is not one."""
    if value is None or (isinstance(value, dict) and not value):
        return []
    return value if isinstance(value, list) else [value]


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_LOGIN_ID): cv.string,
        vol.Optional(CONF_CREDENTIALS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_START_OFF, default=False): cv.boolean,
    })])
}, extra=vol.ALLOW_EXTRA)

# Currently no attributes but it might change later
APPLE_TV_SCAN_SCHEMA = vol.Schema({})

APPLE_TV_AUTHENTICATE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
})


def request_configuration(hass, config, atv, credentials):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    @asyncio.coroutine
    def configuration_callback(callback_data):
        """Handle the submitted configuration."""
        from pyatv import exceptions
        pin = callback_data.get('pin')

        try:
            yield from atv.airplay.finish_authentication(pin)
            hass.components.persistent_notification.async_create(
                'Authentication succeeded!<br /><br />Add the following '
                'to credentials: in your apple_tv configuration:<br /><br />'
                '{0}'.format(credentials),
                title=NOTIFICATION_AUTH_TITLE,
                notification_id=NOTIFICATION_AUTH_ID)
        except exceptions.DeviceAuthenticationError as ex:
            hass.components.persistent_notification.async_create(
                'Authentication failed! Did you enter correct PIN?<br /><br />'
                'Details: {0}'.format(ex),
                title=NOTIFICATION_AUTH_TITLE,
                notification_id=NOTIFICATION_AUTH_ID)

        hass.async_add_job(configurator.request_done, instance)

    instance = configurator.request_config(
        'Apple TV Authentication', configuration_callback,
        description='Please enter PIN code shown on screen.',
        submit_caption='Confirm',
        fields=[{'id': 'pin', 'name': 'PIN Code', 'type': 'password'}]
    )


@asyncio.coroutine
def scan_for_apple_tvs(hass):
    """Scan for devices and present a notification of the ones found."""
    import pyatv
    atvs = yield from pyatv.scan_for_apple_tvs(hass.loop, timeout=3)

    devices = []
    for atv in atvs:
        login_id = atv.login_id
        if login_id is None:
            login_id = 'Home Sharing disabled'
        devices.append('Name: {0}<br />Host: {1}<br />Login ID: {2}'.format(
            atv.name, atv.address, login_id))

    if not devices:
        devices = ['No device(s) found']

    hass.components.persistent_notification.async_create(
        'The following devices were found:<br /><br />' +
        '<br /><br />'.join(devices),
        title=NOTIFICATION_SCAN_TITLE,
        notification_id=NOTIFICATION_SCAN_ID)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Apple TV component."""
    if DATA_APPLE_TV not in hass.data:
        hass.data[DATA_APPLE_TV] = {}

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle service calls."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if service.service == SERVICE_SCAN:
            hass.async_add_job(scan_for_apple_tvs, hass)
            return

        if entity_ids:
            devices = [device for device in hass.data[DATA_ENTITIES]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_ENTITIES]

        for device in devices:
            if service.service != SERVICE_AUTHENTICATE:
                continue

            atv = device.atv
            credentials = yield from atv.airplay.generate_credentials()
            yield from atv.airplay.load_credentials(credentials)
            _LOGGER.debug('Generated new credentials: %s', credentials)
            yield from atv.airplay.start_authentication()
            hass.async_add_job(request_configuration,
                               hass, config, atv, credentials)

    @asyncio.coroutine
    def atv_discovered(service, info):
        """Set up an Apple TV that was auto discovered."""
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

    hass.services.async_register(
        DOMAIN, SERVICE_SCAN, async_service_handler,
        schema=APPLE_TV_SCAN_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_AUTHENTICATE, async_service_handler,
        schema=APPLE_TV_AUTHENTICATE_SCHEMA)

    return True


@asyncio.coroutine
def _setup_atv(hass, atv_config):
    """Set up an Apple TV."""
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

    hass.async_create_task(discovery.async_load_platform(
        hass, 'media_player', DOMAIN, atv_config))

    hass.async_create_task(discovery.async_load_platform(
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
        """Return true if device is on or off."""
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
