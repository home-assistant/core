"""Device tracker for Synology SRM routers."""
from __future__ import annotations

import logging

import synology_srm
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

ATTRIBUTE_ALIAS = {
    "band": None,
    "connection": None,
    "current_rate": None,
    "dev_type": None,
    "hostname": None,
    "ip6_addr": None,
    "ip_addr": None,
    "is_baned": "is_banned",
    "is_beamforming_on": None,
    "is_guest": None,
    "is_high_qos": None,
    "is_low_qos": None,
    "is_manual_dev_type": None,
    "is_manual_hostname": None,
    "is_online": None,
    "is_parental_controled": "is_parental_controlled",
    "is_qos": None,
    "is_wireless": None,
    "mac": None,
    "max_rate": None,
    "mesh_node_id": None,
    "rate_quality": None,
    "signalstrength": "signal_strength",
    "transferRXRate": "transfer_rx_rate",
    "transferTXRate": "transfer_tx_rate",
}


def get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner | None:
    """Validate the configuration and return Synology SRM scanner."""
    scanner = SynologySrmDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SynologySrmDeviceScanner(DeviceScanner):
    """This class scans for devices connected to a Synology SRM router."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.client = synology_srm.Client(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            https=config[CONF_SSL],
        )

        if not config[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()

        self.devices = []
        self.success_init = self._update_info()

        _LOGGER.info("Synology SRM scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device["mac"] for device in self.devices]

    def get_extra_attributes(self, device) -> dict:
        """Get the extra attributes of a device."""
        device = next(
            (result for result in self.devices if result["mac"] == device), None
        )
        filtered_attributes: dict[str, str] = {}
        if not device:
            return filtered_attributes
        for attribute, alias in ATTRIBUTE_ALIAS.items():
            if (value := device.get(attribute)) is None:
                continue
            attr = alias or attribute
            filtered_attributes[attr] = value
        return filtered_attributes

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result["hostname"] for result in self.devices if result["mac"] == device
        ]

        if filter_named:
            return filter_named[0]

        return None

    def _update_info(self):
        """Check the router for connected devices."""
        _LOGGER.debug("Scanning for connected devices")

        try:
            self.devices = self.client.core.get_network_nsm_device({"is_online": True})
        except synology_srm.http.SynologyException as ex:
            _LOGGER.error("Error with the Synology SRM: %s", ex)
            return False

        _LOGGER.debug("Found %d device(s) connected to the router", len(self.devices))

        return True
