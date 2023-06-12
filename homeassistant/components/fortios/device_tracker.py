"""Support to use FortiOS device like FortiGate as device tracker.

This component is part of the device_tracker platform.
"""
from __future__ import annotations

import logging

from awesomeversion import AwesomeVersion
from fortiosapi import FortiOSAPI
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> FortiOSDeviceScanner | None:
    """Validate the configuration and return a FortiOS scanner."""
    scanner = FortiOSDeviceScanner(config[DOMAIN])

    return scanner if scanner.initialize() else None


class FortiOSDeviceScanner(DeviceScanner):
    """Class which queries a FortiOS unit for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.token = config[CONF_TOKEN]
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.last_results = {}
        self.success_init = None
        self._fgt = self._get_fortios_obj()

        if self._fgt is not None:
            # Test the router is accessible.
            data = self._get_fortios_data()
            self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        _LOGGER.debug("scan_devices()")

        self._update_info()
        return [client["mac"] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        _LOGGER.debug("get_device_name(%s)", device)

        if not self.last_results:
            _LOGGER.error("No last_results to get device names")
            return None
        for client in self.last_results:
            if client["mac"] == device:
                _LOGGER.debug("%s = get_device_name(%s)", client["name"], device)
                return client["name"]
        return None

    def _update_info(self):
        """Ensure the information from the FortiOS device is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("_update_info()")

        if not self.success_init:
            return False

        if not (data := self._get_fortios_data()):
            return False

        self.last_results = data.values()

        _LOGGER.debug("_update_info, last_results=%s", self.last_results)
        return True

    def _get_fortios_data(self):
        """Retrieve data from FortiOS device and return parsed result."""
        _LOGGER.debug("_get_fortios_data()")

        data = self._fgt.monitor(
            "user/device/query",
            "",
            parameters={"filter": "format=master_mac|hostname|is_online"},
        )
        devices = {}
        try:
            for client in data["results"]:
                if "is_online" in client and "master_mac" in client:
                    if client["is_online"]:
                        hostname = client["master_mac"].replace(":", "_")

                        if "hostname" in client:
                            hostname = client["hostname"]

                        devices[client["master_mac"]] = {
                            "mac": client["master_mac"].upper(),
                            "name": hostname,
                        }
        except KeyError as kex:
            _LOGGER.error("Key not found in clients: %s", kex)

        return devices

    def _get_fortios_obj(self):
        """Validate the configuration and return a FortiOSAPI object."""
        _LOGGER.debug("_get_fortios_obj()")

        fgt = FortiOSAPI()

        try:
            fgt.tokenlogin(self.host, self.token, self.verify_ssl, None, 12, "root")
        except ConnectionError as ex:
            _LOGGER.error("ConnectionError to FortiOS API: %s", ex)
            return None
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Failed to login to FortiOS API: %s", ex)
            return None

        system_status = fgt.monitor("system/status", "")

        current_version = AwesomeVersion(system_status["version"])
        minimum_version = AwesomeVersion("6.4.3")
        if current_version < minimum_version:
            _LOGGER.error(
                "Unsupported FortiOS version: %s. Version %s and newer are supported",
                current_version,
                minimum_version,
            )
            return None

        return fgt
