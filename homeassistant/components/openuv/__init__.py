"""
Support for UV data from openuv.io.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/openuv/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_BINARY_SENSORS, CONF_ELEVATION,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL, CONF_SENSORS)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import DOMAIN

REQUIREMENTS = ['pyopenuv==1.0.4']
_LOGGER = logging.getLogger(__name__)

DATA_OPENUV_CLIENT = 'data_client'
DATA_OPENUV_LISTENER = 'data_listener'
DATA_PROTECTION_WINDOW = 'protection_window'
DATA_UV = 'uv'

DEFAULT_ATTRIBUTION = 'Data provided by OpenUV'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

NOTIFICATION_ID = 'openuv_notification'
NOTIFICATION_TITLE = 'OpenUV Component Setup'

TOPIC_UPDATE = '{0}_data_update'.format(DOMAIN)

TYPE_CURRENT_OZONE_LEVEL = 'current_ozone_level'
TYPE_CURRENT_UV_INDEX = 'current_uv_index'
TYPE_CURRENT_UV_LEVEL = 'current_uv_level'
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
    TYPE_CURRENT_UV_LEVEL: ('Current UV Level', 'mdi:weather-sunny', None),
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
    DOMAIN:
        vol.Schema({
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_ELEVATION): float,
            vol.Optional(CONF_LATITUDE): cv.latitude,
            vol.Optional(CONF_LONGITUDE): cv.longitude,
            vol.Optional(CONF_BINARY_SENSORS, default={}):
                BINARY_SENSOR_SCHEMA,
            vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
                cv.time_period,
        })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the OpenUV component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_OPENUV_CLIENT] = {}
    hass.data[DOMAIN][DATA_OPENUV_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    elevation = conf.get(CONF_ELEVATION, hass.config.elevation)

    identifier = '{0}, {1}'.format(latitude, longitude)

    if identifier not in configured_instances(hass):
        hass.async_add_job(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_API_KEY: conf[CONF_API_KEY],
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_ELEVATION: elevation,
                    CONF_BINARY_SENSORS: conf[CONF_BINARY_SENSORS],
                    CONF_SENSORS: conf[CONF_SENSORS],
                }))

    hass.data[DOMAIN][CONF_SCAN_INTERVAL] = conf[CONF_SCAN_INTERVAL]

    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenUV as config entry."""
    from pyopenuv import Client
    from pyopenuv.errors import OpenUvError

    try:
        websession = aiohttp_client.async_get_clientsession(hass)
        openuv = OpenUV(
            Client(
                config_entry.data[CONF_API_KEY],
                config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
                config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
                websession,
                altitude=config_entry.data.get(
                    CONF_ELEVATION, hass.config.elevation)),
            config_entry.data.get(CONF_BINARY_SENSORS, {}).get(
                CONF_MONITORED_CONDITIONS, list(BINARY_SENSORS)),
            config_entry.data.get(CONF_SENSORS, {}).get(
                CONF_MONITORED_CONDITIONS, list(SENSORS)))
        await openuv.async_update()
        hass.data[DOMAIN][DATA_OPENUV_CLIENT][config_entry.entry_id] = openuv
    except OpenUvError as err:
        _LOGGER.error('An error occurred: %s', str(err))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    for component in ('binary_sensor', 'sensor'):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            config_entry, component))

    async def refresh_sensors(event_time):
        """Refresh OpenUV data."""
        _LOGGER.debug('Refreshing OpenUV data')
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_OPENUV_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass, refresh_sensors,
            hass.data[DOMAIN][CONF_SCAN_INTERVAL])

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    for component in ('binary_sensor', 'sensor'):
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    hass.data[DOMAIN][DATA_OPENUV_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_OPENUV_LISTENER].pop(
        config_entry.entry_id)
    remove_listener()

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, client, binary_sensor_conditions, sensor_conditions):
        """Initialize."""
        self.binary_sensor_conditions = binary_sensor_conditions
        self.client = client
        self.data = {}
        self.sensor_conditions = sensor_conditions

    async def async_update(self):
        """Update sensor/binary sensor data."""
        if TYPE_PROTECTION_WINDOW in self.binary_sensor_conditions:
            data = await self.client.uv_protection_window()
            self.data[DATA_PROTECTION_WINDOW] = data

        if any(c in self.sensor_conditions for c in SENSORS):
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
