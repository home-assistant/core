"""Sensor for SigFox devices."""
import datetime
import json
import logging
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)
API_URL = "https://backend.sigfox.com/api/"
CONF_API_LOGIN = "api_login"
CONF_API_PASSWORD = "api_password"
DEFAULT_NAME = "sigfox"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_LOGIN): cv.string,
        vol.Required(CONF_API_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sigfox sensor."""
    api_login = config[CONF_API_LOGIN]
    api_password = config[CONF_API_PASSWORD]
    name = config[CONF_NAME]
    try:
        sigfox = SigfoxAPI(api_login, api_password)
    except ValueError:
        return False
    auth = sigfox.auth
    devices = sigfox.devices

    sensors = []
    for device in devices:
        sensors.append(SigfoxDevice(device, auth, name))
    add_entities(sensors, True)


def epoch_to_datetime(epoch_time):
    """Take an ms since epoch and return datetime string."""
    return datetime.datetime.fromtimestamp(epoch_time).isoformat()


class SigfoxAPI:
    """Class for interacting with the SigFox API."""

    def __init__(self, api_login, api_password):
        """Initialise the API object."""
        self._auth = requests.auth.HTTPBasicAuth(api_login, api_password)
        if self.check_credentials():
            device_types = self.get_device_types()
            self._devices = self.get_devices(device_types)

    def check_credentials(self):
        """Check API credentials are valid."""
        url = urljoin(API_URL, "devicetypes")
        response = requests.get(url, auth=self._auth, timeout=10)
        if response.status_code != 200:
            if response.status_code == 401:
                _LOGGER.error("Invalid credentials for Sigfox API")
            else:
                _LOGGER.error(
                    "Unable to login to Sigfox API, error code %s",
                    str(response.status_code),
                )
            raise ValueError("Sigfox integration not set up")
        return True

    def get_device_types(self):
        """Get a list of device types."""
        url = urljoin(API_URL, "devicetypes")
        response = requests.get(url, auth=self._auth, timeout=10)
        device_types = []
        for device in json.loads(response.text)["data"]:
            device_types.append(device["id"])
        return device_types

    def get_devices(self, device_types):
        """Get the device_id of each device registered."""
        devices = []
        for unique_type in device_types:
            location_url = f"devicetypes/{unique_type}/devices"
            url = urljoin(API_URL, location_url)
            response = requests.get(url, auth=self._auth, timeout=10)
            devices_data = json.loads(response.text)["data"]
            for device in devices_data:
                devices.append(device["id"])
        return devices

    @property
    def auth(self):
        """Return the API authentication."""
        return self._auth

    @property
    def devices(self):
        """Return the list of device_id."""
        return self._devices


class SigfoxDevice(Entity):
    """Class for single sigfox device."""

    def __init__(self, device_id, auth, name):
        """Initialise the device object."""
        self._device_id = device_id
        self._auth = auth
        self._message_data = {}
        self._name = f"{name}_{device_id}"
        self._state = None

    def get_last_message(self):
        """Return the last message from a device."""
        device_url = f"devices/{self._device_id}/messages?limit=1"
        url = urljoin(API_URL, device_url)
        response = requests.get(url, auth=self._auth, timeout=10)
        data = json.loads(response.text)["data"][0]
        payload = bytes.fromhex(data["data"]).decode("utf-8")
        lat = data["rinfos"][0]["lat"]
        lng = data["rinfos"][0]["lng"]
        snr = data["snr"]
        epoch_time = data["time"]
        return {
            "lat": lat,
            "lng": lng,
            "payload": payload,
            "snr": snr,
            "time": epoch_to_datetime(epoch_time),
        }

    def update(self):
        """Fetch the latest device message."""
        self._message_data = self.get_last_message()
        self._state = self._message_data["payload"]

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
