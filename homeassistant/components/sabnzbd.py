"""
Support for monitoring an SABnzbd NZB client.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sabnzbd/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.discovery import SERVICE_SABNZBD
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_HOST, CONF_API_KEY, CONF_NAME, CONF_PORT, CONF_SENSORS, CONF_SSL,
    ATTR_ENTITY_ID)
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pysabnzbd==1.0.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sabnzbd'

_CONFIGURING = {}

ATTR_SPEED = 'speed'
BASE_URL_FORMAT = '{}://{}:{}/'
CONFIG_FILE = 'sabnzbd.conf'
CONF_SAB_API = 'sab_api'
DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'SABnzbd'
DEFAULT_PORT = 8080
DEFAULT_SPEED_LIMIT = '100'
DEFAULT_SSL = False

SERVICE_PAUSE = 'pause'
SERVICE_RESUME = 'resume'
SERVICE_SET_SPEED = 'set_speed'

SIGNAL_SABNZBD_UPDATED_BASE = 'sabnzbd_updated.{}'

SENSOR_TYPES = {
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

PAUSE_RESUME_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids
})

SPEED_LIMIT_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SENSORS):
            vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    })], cv.value_is_unique_in_list(CONF_NAME)),
}, extra=vol.ALLOW_EXTRA)


async def async_check_sabnzbd(sab_api):
    """Check if we can reach SABnzbd."""
    from pysabnzbd import SabnzbdApiException

    try:
        await sab_api.check_available()
        return True
    except SabnzbdApiException as err:
        _LOGGER.error(err)
        return False


async def async_configure_discovered(hass, discovery_info, component):
    """Configure a discovered SABnzbd instance. Request API key if needed."""
    from pysabnzbd import SabnzbdApi

    host = discovery_info[CONF_HOST]
    port = discovery_info[CONF_PORT]
    name = discovery_info.get('hostname', host).strip('.').replace('.', '_')
    use_ssl = discovery_info.get('properties', {}).get('https', '0') == '1'
    uri_scheme = 'https' if use_ssl else 'http'
    base_url = BASE_URL_FORMAT.format(uri_scheme, host, port)
    conf = await hass.async_add_job(load_json,
                                    hass.config.path(CONFIG_FILE))
    api_key = conf.get(base_url, {}).get(CONF_API_KEY, '')
    sab_api = SabnzbdApi(base_url, api_key)
    if await async_check_sabnzbd(sab_api):
        sab_entity = async_setup_sabnzbd(hass, sab_api, {}, name)
        await component.async_add_entities([sab_entity])
    else:
        async_request_configuration(hass, discovery_info, base_url, name,
                                    component)


async def async_configure_sabnzbd(hass, config):
    """Configure a declared SABnzbd instance."""
    from pysabnzbd import SabnzbdApi

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    use_ssl = config.get(CONF_SSL)
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    uri_scheme = 'https' if use_ssl else 'http'
    base_url = BASE_URL_FORMAT.format(uri_scheme, host, port)
    sab_api = SabnzbdApi(base_url, api_key)
    if await async_check_sabnzbd(sab_api):
        return async_setup_sabnzbd(hass, sab_api, config, name)


async def async_setup(hass, config):
    """Setup the SABnzbd component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    async def sabnzbd_discovered(service, info):
        """Handle service discovery."""
        await async_configure_discovered(hass, info, component)

    discovery.async_listen(hass, SERVICE_SABNZBD, sabnzbd_discovered)

    sabnzbd_config = config.get(DOMAIN)
    entities = []
    for conf in sabnzbd_config:
        sab_entity = await async_configure_sabnzbd(hass, conf)
        if sab_entity:
            entities.append(sab_entity)

    async def async_service_handler(service):
        """Handle service calls."""
        sab_entities = component.async_extract_from_service(service)
        for entity in sab_entities:
            if service.service == SERVICE_PAUSE:
                await entity.async_pause_queue()
            elif service.service == SERVICE_RESUME:
                await entity.async_resume_queue()
            elif service.service == SERVICE_SET_SPEED:
                speed = service.data.get(ATTR_SPEED)
                await entity.async_set_queue_speed(speed)

    hass.services.async_register(DOMAIN, SERVICE_PAUSE,
                                 async_service_handler,
                                 schema=PAUSE_RESUME_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_RESUME,
                                 async_service_handler,
                                 schema=PAUSE_RESUME_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_SET_SPEED,
                                 async_service_handler,
                                 schema=SPEED_LIMIT_SCHEMA)

    if entities:
        await component.async_add_entities(entities)
    return True


@callback
def async_setup_sabnzbd(hass, sab_api, config, name):
    """Create SABnzbd entity and associated sensor entities."""
    sab_entity = SabnzbdEntity(sab_api, name, config.get(CONF_SENSORS, {}))
    if config.get(CONF_SENSORS):
        data = {CONF_SAB_API: sab_entity, CONF_SENSORS: config[CONF_SENSORS]}
        hass.async_add_job(
            discovery.async_load_platform(hass, SENSOR_DOMAIN, DOMAIN, data))
    return sab_entity


@callback
def async_request_configuration(hass, config, host, name, component):
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
            """Setup was successful."""
            conf = load_json(hass.config.path(CONFIG_FILE))
            conf[host] = {CONF_API_KEY: api_key}
            save_json(hass.config.path(CONFIG_FILE), conf)
            req_config = _CONFIGURING.pop(host)
            configurator.request_done(req_config)

        hass.async_add_job(success)
        sab_entity = async_setup_sabnzbd(hass, sab_api, {}, name)
        await component.async_add_entities([sab_entity])

    _CONFIGURING[host] = configurator.async_request_config(
        DEFAULT_NAME,
        async_configuration_callback,
        description='Enter the API Key',
        submit_caption='Confirm',
        fields=[{'id': CONF_API_KEY, 'name': 'API Key', 'type': ''}]
    )


class SabnzbdEntity(Entity):
    """Representation of a SABnzbd Usenet client instance."""

    def __init__(self, sab_api, name, sensors):
        """Initialize entity."""
        self._name = " ".join(name.split())
        self._state = None

        self.identifier = self._name.lower().replace(' ', '_')
        self.entity_id = '{}.{}'.format(DOMAIN, self.identifier)
        self.sab_api = sab_api
        self.sensors = sensors
        self.updated_signal = SIGNAL_SABNZBD_UPDATED_BASE.format(
            self.identifier)

    @property
    def name(self):
        """Return the name of this SABnzbd instance."""
        return self._name

    @property
    def state(self):
        """Return the state of this SABnzbd instance."""
        return self._state

    async def async_update(self):
        """Update SABnzbd API data and send signal to update sensors."""
        from pysabnzbd import SabnzbdApiException
        try:
            await self.sab_api.refresh_data()
            self._state = self.sab_api.queue.get('status')
            async_dispatcher_send(self.hass, self.updated_signal, None)
        except SabnzbdApiException as err:
            _LOGGER.error(err)

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
