"""Support for Mojio Platform."""
import logging

from mojio_sdk.api import API
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE = "include"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_INCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Set up the DeviceScanner and check if login is valid."""
    scanner = MojioDeviceScanner(config, see)
    if not scanner.login(hass):
        _LOGGER.error("Mojio authentication failed")
        return False
    return True


class MojioDeviceScanner:
    """Define a scanner for the Mojio platform."""

    def __init__(self, config, see):
        """Initialize MojioDeviceScanner."""

        self._include = config.get(CONF_INCLUDE)
        self._see = see

        self._api = API(
            config.get(CONF_DOMAIN),
            config.get(CONF_CLIENT_ID),
            config.get(CONF_CLIENT_SECRET),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
        )

    def setup(self, hass):
        """Set up a timer and start gathering devices."""
        self._refresh()
        track_utc_time_change(hass, lambda now: self._refresh(), minute=range(0, 60, 5))

    def login(self, hass):
        """Perform a login on the Mojio API."""
        if self._api.login():
            self.setup(hass)
            return True
        return False

    def _refresh(self) -> None:
        """Refresh device information from the platform."""
        try:
            vehicles = self._api.get_vehicles()

            for vehicle in vehicles:
                if not self._include or vehicle.license_plate in self._include:

                    # if vehicle.active or vehicle.current_address is None:
                    #     device.get_map_details()

                    self._see(
                        dev_id=vehicle.licence_plate.replace("-", "_"),
                        gps=(vehicle.location.latitude, vehicle.location.longitude),
                        # attributes=vehicle.state_attributes,
                        icon="mdi:car",
                    )

        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Could not connect to Mojio")
