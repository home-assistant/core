"""Support for Cisco Mobility Express."""

from __future__ import annotations

import logging

from ciscomobilityexpress.ciscome import CiscoMobilityExpress
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> CiscoMEDeviceScanner | None:
    """Validate the configuration and return a Cisco ME scanner."""

    config = config[DEVICE_TRACKER_DOMAIN]

    controller = CiscoMobilityExpress(
        config[CONF_HOST],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_SSL],
        config[CONF_VERIFY_SSL],
    )
    if not controller.is_logged_in():
        return None
    return CiscoMEDeviceScanner(controller)


class CiscoMEDeviceScanner(DeviceScanner):
    """Scanner for devices associated to a Cisco ME controller."""

    def __init__(self, controller):
        """Initialize the scanner."""
        self.controller = controller
        self.last_results = {}

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.macaddr for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return next(
            (result.clId for result in self.last_results if result.macaddr == device),
            None,
        )

    def get_extra_attributes(self, device):
        """Get extra attributes of a device.

        Some known extra attributes that may be returned in the device tuple
        include SSID, PT (eg 802.11ac), devtype (eg iPhone 7) among others.
        """
        device = next(
            (result for result in self.last_results if result.macaddr == device), None
        )
        return device._asdict()

    def _update_info(self):
        """Check the Cisco ME controller for devices."""
        self.last_results = self.controller.get_associated_devices()
        _LOGGER.debug(
            "Cisco Mobility Express controller returned: %s", self.last_results
        )
