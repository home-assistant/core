"""
Sensor for SigFox devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sigfox/
"""
import logging
import datetime
import json
import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)
API_URL = 'https://backend.sigfox.com/api/'
CONF_API_LOGIN = 'api_login'
CONF_API_PASSWORD = 'api_password'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_LOGIN): cv.string,
    vol.Required(CONF_API_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sigfox sensor."""
    api_login = config[CONF_API_LOGIN]
    api_password = config[CONF_API_PASSWORD]
    sigfox = SigfoxAPI(api_login, api_password)
    auth = sigfox.auth
    devices = sigfox.devices

    sensors = []
    for device in devices:
        sensors.append(SigfoxDevice(device, auth))
    add_devices(sensors, True)


def epoch_to_datetime(epoch_time):
    """Take an ms since epoch and return datetime string."""
    return datetime.datetime.fromtimestamp(epoch_time).isoformat()


class SigfoxAPI(object):
    """Class for interacting with the SigFox API."""

    def __init__(self, api_login, api_password):
        """Initialise the API object."""
        self._auth = requests.auth.HTTPBasicAuth(api_login, api_password)
        response = requests.get(API_URL + 'devicetypes', auth=self._auth)
        if response.status_code != 200:
            _LOGGER.warning(
                "Unable to login to Sigfox API: %s", str(response.status_code))
            self._devices = []
            return
        device_types = self.get_device_types()
        self._devices = self.get_devices(device_types)

    def get_device_types(self):
        """Get a list of device types."""
        url = API_URL + 'devicetypes'
        response = requests.get(url, auth=self._auth)
        device_types = []
        for device in json.loads(response.text)['data']:
            device_types.append(device['id'])
        return device_types

    def get_devices(self, device_types):
        """Get the device_id of each device registered."""
        devices = []
        for unique_type in device_types:
            url = API_URL + 'devicetypes/' + unique_type + '/devices'
            response = requests.get(url, auth=self._auth)
            devices_data = json.loads(response.text)['data']
            for device in devices_data:
                devices.append(device['id'])
        return devices

    @property
    def auth(self):
        """Return the API authentification."""
        return self._auth

    @property
    def devices(self):
        """Return the list of device_id."""
        return self._devices


class SigfoxDevice(Entity):
    """Class for single sigfox device."""

    def __init__(self, device_id, auth):
        """Initialise the device object."""
        self._device_id = device_id
        self._auth = auth
        self._message_data = {}
        self._name = 'sigfox_' + device_id
        self._state = None

    def get_last_message(self):
        """Return the last message from a device."""
        url = API_URL + 'devices/' + self._device_id + '/messages?limit=1'
        response = requests.get(url, auth=self._auth)
        data = json.loads(response.text)['data'][0]
        payload = bytes.fromhex(data['data']).decode('utf-8')
        lat = data['rinfos'][0]['lat']
        lng = data['rinfos'][0]['lng']
        snr = data['snr']
        epoch_time = data['time']
        return {'lat': lat,
                'lng': lng,
                'payload': payload,
                'snr': snr,
                'time': epoch_to_datetime(epoch_time)}

    def update(self):
        """Fetch the latest device message."""
        self._message_data = self.get_last_message()
        self._state = self._message_data['payload']

    @property
    def name(self):
        """Return the HA name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the payload of the last message."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return other details about the last message."""
        return self._message_data
