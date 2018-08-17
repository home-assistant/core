"""
Support for data from openuv.io.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/openuv/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_BINARY_SENSORS, CONF_ELEVATION,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL, CONF_SENSORS)
from homeassistant.helpers import (
    aiohttp_client, config_validation as cv, discovery)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['pyopenuv==1.0.1']
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'openuv'

DATA_PROTECTION_WINDOW = 'protection_window'
DATA_UV = 'uv'

DEFAULT_ATTRIBUTION = 'Data provided by OpenUV'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

NOTIFICATION_ID = 'openuv_notification'
NOTIFICATION_TITLE = 'OpenUV Component Setup'

TOPIC_UPDATE = '{0}_data_update'.format(DOMAIN)

TYPE_CURRENT_OZONE_LEVEL = 'current_ozone_level'
TYPE_CURRENT_UV_INDEX = 'current_uv_index'
TYPE_MAX_UV_INDEX = 'max_uv_index'
TYPE_PROTECTION_WINDOW = 'uv_protection_window'
TYPE_SAFE_EXPOSURE_TIME_1 = 'safe_exposure_time_type_1'
TYPE_SAFE_EXPOSURE_TIME_2 = 'safe_exposure_time_type_2'
TYPE_SAFE_EXPOSURE_TIME_3 = 'safe_exposure_time_type_3'
TYPE_SAFE_EXPOSURE_TIME_4 = 'safe_exposure_time_type_4'
TYPE_SAFE_EXPOSURE_TIME_5 = 'safe_exposure_time_type_5'
TYPE_SAFE_EXPOSURE_TIME_6 = 'safe_exposure_time_type_6'

BINARY_SENSORS = {
    TYPE_PROTECTION_WINDOW: ('Protection Window', 'mdi:sunglasses')
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)])
})

SENSORS = {
    TYPE_CURRENT_OZONE_LEVEL: (
        'Current Ozone Level', 'mdi:vector-triangle', 'du'),
    TYPE_CURRENT_UV_INDEX: ('Current UV Index', 'mdi:weather-sunny', 'index'),
    TYPE_MAX_UV_INDEX: ('Max UV Index', 'mdi:weather-sunny', 'index'),
    TYPE_SAFE_EXPOSURE_TIME_1: (
        'Skin Type 1 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_2: (
        'Skin Type 2 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_3: (
        'Skin Type 3 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_4: (
        'Skin Type 4 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_5: (
        'Skin Type 5 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_6: (
        'Skin Type 6 Safe Exposure Time', 'mdi:timer', 'minutes'),
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ELEVATION): float,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_BINARY_SENSORS, default={}): BINARY_SENSOR_SCHEMA,
        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
            cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the OpenUV component."""
    from pyopenuv import Client
    from pyopenuv.errors import OpenUvError

    conf = config[DOMAIN]
    api_key = conf[CONF_API_KEY]
    elevation = conf.get(CONF_ELEVATION, hass.config.elevation)
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)

    try:
        websession = aiohttp_client.async_get_clientsession(hass)
        openuv = OpenUV(
            Client(
                api_key, latitude, longitude, websession, altitude=elevation),
            conf[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS] +
            conf[CONF_SENSORS][CONF_MONITORED_CONDITIONS])
        await openuv.async_update()
        hass.data[DOMAIN] = openuv
    except OpenUvError as err:
        _LOGGER.error('An error occurred: %s', str(err))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    for component, schema in [
            ('binary_sensor', conf[CONF_BINARY_SENSORS]),
            ('sensor', conf[CONF_SENSORS]),
    ]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, component, DOMAIN, schema, config))

    async def refresh_sensors(event_time):
        """Refresh OpenUV data."""
        _LOGGER.debug('Refreshing OpenUV data')
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    async_track_time_interval(hass, refresh_sensors, conf[CONF_SCAN_INTERVAL])

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, client, monitored_conditions):
        """Initialize."""
        self._monitored_conditions = monitored_conditions
        self.client = client
        self.data = {}

    async def async_update(self):
        """Update sensor/binary sensor data."""
        if TYPE_PROTECTION_WINDOW in self._monitored_conditions:
            data = await self.client.uv_protection_window()
            self.data[DATA_PROTECTION_WINDOW] = data

        if any(c in self._monitored_conditions for c in SENSORS):
            data = await self.client.uv_index()
            self.data[DATA_UV] = data


class OpenUvEntity(Entity):
    """Define a generic OpenUV entity."""

    def __init__(self, openuv):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._name = None
        self.openuv = openuv

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name
