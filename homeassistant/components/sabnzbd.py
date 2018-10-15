"""
Support for monitoring an SABnzbd NZB client.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sabnzbd/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.discovery import SERVICE_SABNZBD
from homeassistant.const import (
    CONF_HOST, CONF_API_KEY, CONF_NAME, CONF_PORT, CONF_SENSORS, CONF_SSL)
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pysabnzbd==1.0.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sabnzbd'
DATA_SABNZBD = 'sabznbd'

_CONFIGURING = {}

ATTR_SPEED = 'speed'
BASE_URL_FORMAT = '{}://{}:{}/'
CONFIG_FILE = 'sabnzbd.conf'
DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'SABnzbd'
DEFAULT_PORT = 8080
DEFAULT_SPEED_LIMIT = '100'
DEFAULT_SSL = False

UPDATE_INTERVAL = timedelta(seconds=30)

SERVICE_PAUSE = 'pause'
SERVICE_RESUME = 'resume'
SERVICE_SET_SPEED = 'set_speed'

SIGNAL_SABNZBD_UPDATED = 'sabnzbd_updated'

SENSOR_TYPES = {
    'current_status': ['Status', None, 'status'],
    'speed': ['Speed', 'MB/s', 'kbpersec'],
    'queue_size': ['Queue', 'MB', 'mb'],
    'queue_remaining': ['Left', 'MB', 'mbleft'],
    'disk_size': ['Disk', 'GB', 'diskspacetotal1'],
    'disk_free': ['Disk Free', 'GB', 'diskspace1'],
    'queue_count': ['Queue Count', None, 'noofslots_total'],
    'day_size': ['Daily Total', 'GB', 'day_size'],
    'week_size': ['Weekly Total', 'GB', 'week_size'],
    'month_size': ['Monthly Total', 'GB', 'month_size'],
    'total_size': ['Total', 'GB', 'total_size'],
}

SPEED_LIMIT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SENSORS):
            vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_check_sabnzbd(sab_api):
    """Check if we can reach SABnzbd."""
    from pysabnzbd import SabnzbdApiException

    try:
        await sab_api.check_available()
        return True
    except SabnzbdApiException:
        _LOGGER.error("Connection to SABnzbd API failed")
        return False


async def async_configure_sabnzbd(hass, config, use_ssl, name=DEFAULT_NAME,
                                  api_key=None):
    """Try to configure Sabnzbd and request api key if configuration fails."""
    from pysabnzbd import SabnzbdApi

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    uri_scheme = 'https' if use_ssl else 'http'
    base_url = BASE_URL_FORMAT.format(uri_scheme, host, port)
    if api_key is None:
        conf = await hass.async_add_job(load_json,
                                        hass.config.path(CONFIG_FILE))
        api_key = conf.get(base_url, {}).get(CONF_API_KEY, '')

    sab_api = SabnzbdApi(base_url, api_key)
    if await async_check_sabnzbd(sab_api):
        async_setup_sabnzbd(hass, sab_api, config, name)
    else:
        async_request_configuration(hass, config, base_url)


async def async_setup(hass, config):
    """Set up the SABnzbd component."""
    async def sabnzbd_discovered(service, info):
        """Handle service discovery."""
        ssl = info.get('properties', {}).get('https', '0') == '1'
        await async_configure_sabnzbd(hass, info, ssl)

    discovery.async_listen(hass, SERVICE_SABNZBD, sabnzbd_discovered)

    conf = config.get(DOMAIN)
    if conf is not None:
        use_ssl = conf.get(CONF_SSL)
        name = conf.get(CONF_NAME)
        api_key = conf.get(CONF_API_KEY)
        await async_configure_sabnzbd(hass, conf, use_ssl, name, api_key)
    return True


@callback
def async_setup_sabnzbd(hass, sab_api, config, name):
    """Set up SABnzbd sensors and services."""
    sab_api_data = SabnzbdApiData(sab_api, name, config.get(CONF_SENSORS, {}))

    if config.get(CONF_SENSORS):
        hass.data[DATA_SABNZBD] = sab_api_data
        hass.async_create_task(
            discovery.async_load_platform(hass, 'sensor', DOMAIN, {}, config))

    async def async_service_handler(service):
        """Handle service calls."""
        if service.service == SERVICE_PAUSE:
            await sab_api_data.async_pause_queue()
        elif service.service == SERVICE_RESUME:
            await sab_api_data.async_resume_queue()
        elif service.service == SERVICE_SET_SPEED:
            speed = service.data.get(ATTR_SPEED)
            await sab_api_data.async_set_queue_speed(speed)

    hass.services.async_register(DOMAIN, SERVICE_PAUSE,
                                 async_service_handler,
                                 schema=vol.Schema({}))

    hass.services.async_register(DOMAIN, SERVICE_RESUME,
                                 async_service_handler,
                                 schema=vol.Schema({}))

    hass.services.async_register(DOMAIN, SERVICE_SET_SPEED,
                                 async_service_handler,
                                 schema=SPEED_LIMIT_SCHEMA)

    async def async_update_sabnzbd(now):
        """Refresh SABnzbd queue data."""
        from pysabnzbd import SabnzbdApiException
        try:
            await sab_api.refresh_data()
            async_dispatcher_send(hass, SIGNAL_SABNZBD_UPDATED, None)
        except SabnzbdApiException as err:
            _LOGGER.error(err)

    async_track_time_interval(hass, async_update_sabnzbd, UPDATE_INTERVAL)


@callback
def async_request_configuration(hass, config, host):
    """Request configuration steps from the user."""
    from pysabnzbd import SabnzbdApi

    configurator = hass.components.configurator
    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.async_notify_errors(
            _CONFIGURING[host],
            'Failed to register, please try again.')

        return

    async def async_configuration_callback(data):
        """Handle configuration changes."""
        api_key = data.get(CONF_API_KEY)
        sab_api = SabnzbdApi(host, api_key)
        if not await async_check_sabnzbd(sab_api):
            return

        def success():
            """Signal successful setup."""
            conf = load_json(hass.config.path(CONFIG_FILE))
            conf[host] = {CONF_API_KEY: api_key}
            save_json(hass.config.path(CONFIG_FILE), conf)
            req_config = _CONFIGURING.pop(host)
            configurator.request_done(req_config)

        hass.async_add_job(success)
        async_setup_sabnzbd(hass, sab_api, config,
                            config.get(CONF_NAME, DEFAULT_NAME))

    _CONFIGURING[host] = configurator.async_request_config(
        DEFAULT_NAME,
        async_configuration_callback,
        description='Enter the API Key',
        submit_caption='Confirm',
        fields=[{'id': CONF_API_KEY, 'name': 'API Key', 'type': ''}]
    )


class SabnzbdApiData:
    """Class for storing/refreshing sabnzbd api queue data."""

    def __init__(self, sab_api, name, sensors):
        """Initialize component."""
        self.sab_api = sab_api
        self.name = name
        self.sensors = sensors

    async def async_pause_queue(self):
        """Pause Sabnzbd queue."""
        from pysabnzbd import SabnzbdApiException
        try:
            return await self.sab_api.pause_queue()
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    async def async_resume_queue(self):
        """Resume Sabnzbd queue."""
        from pysabnzbd import SabnzbdApiException
        try:
            return await self.sab_api.resume_queue()
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    async def async_set_queue_speed(self, limit):
        """Set speed limit for the Sabnzbd queue."""
        from pysabnzbd import SabnzbdApiException
        try:
            return await self.sab_api.set_speed_limit(limit)
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    def get_queue_field(self, field):
        """Return the value for the given field from the Sabnzbd queue."""
        return self.sab_api.queue.get(field)
