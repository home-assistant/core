"""Support for FleetGO Platform."""
import logging

import requests
from ritassist import API
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_INCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Set up the DeviceScanner and check if login is valid."""
    scanner = FleetGoDeviceScanner(config, see)
    if not scanner.login(hass):
        _LOGGER.error("FleetGO authentication failed")
        return False
    return True


class FleetGoDeviceScanner:
    """Define a scanner for the FleetGO platform."""

    def __init__(self, config, see):
        """Initialize FleetGoDeviceScanner."""
        self._include = config.get(CONF_INCLUDE)
        self._see = see

        self._api = API(
            config.get(CONF_CLIENT_ID),
            config.get(CONF_CLIENT_SECRET),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
        )

    def setup(self, hass):
        """Set up a timer and start gathering devices."""
        self._refresh()
        track_utc_time_change(
            hass, lambda now: self._refresh(), second=range(0, 60, 30)
        )

    def login(self, hass):
        """Perform a login on the FleetGO API."""
        if self._api.login():
            self.setup(hass)
            return True
        return False

    def _refresh(self) -> None:
        """Refresh device information from the platform."""
        try:
            devices = self._api.get_devices()

            for device in devices:
                if not self._include or device.license_plate in self._include:

                    if device.active or device.current_address is None:
                        device.get_map_details()

                    self._see(
                        dev_id=device.plate_as_id,
                        gps=(device.latitude, device.longitude),
                        attributes=device.state_attributes,
                        icon="mdi:car",
                    )

        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Could not connect to FleetGO")
