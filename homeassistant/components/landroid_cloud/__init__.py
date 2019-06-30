"""Support for Worx Landroid Cloud based lawn mowers."""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_EMAIL, CONF_DEVICE, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval 

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'landroid'
DOMAIN = 'landroid_cloud'
LANDROID_API = 'landroid_cloud_api'
SCAN_INTERVAL = timedelta(seconds=10)
UPDATE_SIGNAL = 'landroid_cloud_update_signal'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICE, default=0): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


API_WORX_SENSORS = {
    'battery': {
        'state': {
            'battery_percent': 'state',
            'battery_voltage': 'battery_voltage',
            'battery_temperature': 'battery_temperature',
            'battery_charge_cycles': 'charge_cycles',
            'battery_charging': 'charging',
        },
        'icon': 'mdi:battery',
        'unit': '%',
        'device_class': None,
    },
    'error': {
        'state': {
            'error_description': 'state',
            'error': 'error_id',
        },
        'icon': None,
        'unit': None,
        'device_class': None,
    },
    'status': {
        'state': {
            'status_description': 'state',
            'blade_time': 'blade_time',
            'work_time': 'work_time',
            'distance': 'distance',
            'status': 'status_id',
            'updated': 'last_update',
            'rssi': 'rssi',
            'yaw': 'yaw',
            'roll': 'roll',
            'pitch': 'pitch',
        },
        'icon': None,
        'unit': None,
        'device_class': None,
    }
}


async def async_setup(hass, config):
    """Set up the Worx Landroid Cloud component."""
    import pyworxcloud

    cloud_email = config[DOMAIN][CONF_EMAIL]
    cloud_password = config[DOMAIN][CONF_PASSWORD]
    cloud_device_id = config[DOMAIN][CONF_DEVICE]

    client = pyworxcloud.WorxCloud(cloud_email,
                                   cloud_password,
                                   cloud_device_id)

    if not client:
        return False

    api = WorxLandroidAPI(hass, client, config)
    async_track_time_interval(hass, api.async_update, SCAN_INTERVAL)
    hass.data[LANDROID_API] = api

    return True


class WorxLandroidAPI:
    """Handle the API calls."""

    def __init__(self, hass, client, config):
        """Set up instance."""
        self._hass = hass
        self._client = client
        self.config = config

        sensor_info = []
        info = {}
        info['name'] = '{}_{}'.format(DEFAULT_NAME,
                                      self._client.name)
        info['friendly'] = self._client.name
        sensor_info.append(info)

        load_platform(self._hass,
                      'sensor',
                      DOMAIN,
                      sensor_info,
                      self.config)

    def get_data(self, sensor_type):
        """Get data from state cache."""
        methods = API_WORX_SENSORS[sensor_type]
        data = {}
        for prop, attr in methods['state'].items():
            prop_data = getattr(self._client, prop)
            data[attr] = prop_data
        return data

    async def async_update(self, now=None):
        """Update the state cache from Landroid API."""
        #self._client.update()
        dispatcher_send(self._hass, UPDATE_SIGNAL)