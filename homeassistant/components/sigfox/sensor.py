"""Sensor for SigFox devices."""

from __future__ import annotations

import datetime
from http import HTTPStatus
import json
import logging
from typing import Any
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)
API_URL = "https://backend.sigfox.com/api/"
CONF_API_LOGIN = "api_login"
CONF_API_PASSWORD = "api_password"
DEFAULT_NAME = "sigfox"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_LOGIN): cv.string,
        vol.Required(CONF_API_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sigfox sensor."""
    api_login = config[CONF_API_LOGIN]
    api_password = config[CONF_API_PASSWORD]
    name = config[CONF_NAME]
    try:
        sigfox = SigfoxAPI(api_login, api_password)
    except ValueError:
        return
    auth = sigfox.auth
    devices = sigfox.devices

    add_entities((SigfoxDevice(device, auth, name) for device in devices), True)


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
        if response.status_code != HTTPStatus.OK:
            if response.status_code == HTTPStatus.UNAUTHORIZED:
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
        return [device["id"] for device in json.loads(response.text)["data"]]

    def get_devices(self, device_types):
        """Get the device_id of each device registered."""
        devices = []
        for unique_type in device_types:
            location_url = f"devicetypes/{unique_type}/devices"
            url = urljoin(API_URL, location_url)
            response = requests.get(url, auth=self._auth, timeout=10)
            devices_data = json.loads(response.text)["data"]
            devices.extend(device["id"] for device in devices_data)
        return devices

    @property
    def auth(self):
        """Return the API authentication."""
        return self._auth

    @property
    def devices(self):
        """Return the list of device_id."""
        return self._devices


class SigfoxDevice(SensorEntity):
    """Class for single sigfox device."""

    def __init__(self, device_id, auth, name):
        """Initialise the device object."""
        self._device_id = device_id
        self._auth = auth
        self._attr_name = f"{name}_{device_id}"

    def get_last_message(self) -> dict[str, Any]:
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

    def update(self) -> None:
        """Fetch the latest device message."""
        self._attr_extra_state_attributes = self.get_last_message()
        self._attr_native_value = self._attr_extra_state_attributes["payload"]
