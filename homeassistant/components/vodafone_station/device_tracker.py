"""Device tracker for Vodafone Station."""
from __future__ import annotations

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import VodafoneStationApi
from .const import _LOGGER, DEFAULT_HOST, DEFAULT_SSL, DEFAULT_USERNAME

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> VodafoneStationDeviceScanner | None:
    """Return the Vodafone Station device scanner."""
    scanner = VodafoneStationDeviceScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class VodafoneStationDeviceScanner(DeviceScanner):
    """Scan Vodafone Station devices."""

    def __init__(self, config) -> None:
        """Initialize the scanner."""

        self.api = VodafoneStationApi(config)

        self.last_results: list[dict] = []

        self.api.login()
        data = self.api.overview()
        self.api.logout()

        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client["mac"] == device:
                return client["name"]
        return None

    def _update_info(self) -> bool:
        """Ensure the information from the Vodafone Station is up to date."""
        if not self.success_init:
            return False

        _LOGGER.debug("Loading data from Vodafone Station")
        if not (data := self.get_router_data()):
            _LOGGER.warning("No data from Vodafone Station")
            return False

        self.last_results = [
            client for client in data.values() if client["status"] == "on"
        ]
        return True

    def get_router_data(self):
        """Retrieve data from Vodafone Station and return parsed result."""

        devices = {}

        try:
            self.api.login()
            data = self.api.overview()
            self.api.logout()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectTimeout,
        ):
            _LOGGER.info("No response from Vodafone Station")
            return devices

        kv_tuples = [(list(v.keys())[0], (list(v.values())[0])) for v in data]
        key_values = {}
        for entry in kv_tuples:
            key_values[entry[0]] = entry[1]

        _LOGGER.debug("kv retrieved: %s", key_values)
        if (
            "wifi_user" not in key_values
            and "wifi_guest" not in key_values
            and "ethernet" not in key_values
        ):
            _LOGGER.info("No device in response from Vodafone Station")
            return devices

        # 'on|smartphone|Telefono Nora (2.4GHz)|00:0a:f5:6d:8b:38|192.168.1.128;'
        arr_devices = []
        arr_wifi_user = key_values["wifi_user"].split(";")
        arr_wifi_user = filter(lambda x: x.strip() != "", arr_wifi_user)
        arr_wifi_guest = key_values["wifi_guest"].split(";")
        arr_wifi_guest = filter(lambda x: x.strip() != "", arr_wifi_guest)
        arr_devices.append(arr_wifi_user)
        arr_devices.append(arr_wifi_guest)
        arr_ethernet = list(key_values["ethernet"].split(";"))
        arr_ethernet = filter(lambda x: x.strip() != "", arr_ethernet)
        arr_ethernet = ["on|" + dev for dev in arr_ethernet]
        arr_devices.append(arr_ethernet)
        arr_devices = [item for sublist in arr_devices for item in sublist]
        _LOGGER.debug("Arr_devices: %s", arr_devices)

        for device_line in arr_devices:
            device_fields = device_line.split("|")
            try:
                devices[device_fields[3]] = {
                    "ip": device_fields[4],
                    "mac": device_fields[3],
                    "status": device_fields[0],
                    "name": device_fields[2],
                }
            except (KeyError, requests.exceptions.RequestException, IndexError):
                _LOGGER.warning("Error processing line: %s", device_line)

        return devices
