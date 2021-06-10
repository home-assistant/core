"""Mawaqit Hub Class."""

import logging

from mawaqit_times_calculator import MawaqitTimesCalculator

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class MawaqitHub:
    """Functions for Mawaqit tests and prayer times."""

    def __init__(self, username, password, latitude, longitude, mosque="", token=""):
        """Initialize the MawaqitHub class."""
        self._username = username
        self._password = password
        self._latitude = latitude
        self._longitude = longitude
        self._mosque = mosque
        self._token = token

        _LOGGER.info(
            self._username,
            self._password,
            self._latitude,
            self._longitude,
            self._mosque,
            self._token,
        )

    def validate_auth(self):
        """Validate authentication."""
        try:
            self._mw_connect = MawaqitTimesCalculator(
                self._latitude,
                self._longitude,
                self._mosque,
                self._username,
                self._password,
                self._token,
            )
            _LOGGER.info(self._mw_connect)
        except Exception:
            raise InvalidAuth

    def validate_coordinates(self):
        """Validate coordinates."""
        if not self._latitude >= -90.0 and self._latitude <= 90.0:
            raise Exception("Invalid latitude")
        elif not self._longitude >= -180.0 and self._longitude <= 180.0:
            raise Exception("Invalid longitude")

    def get_api_token(self, as_dict=False):
        """Fetch API token."""
        try:
            self._token = self._mw_connect.apimawaqit()
            _LOGGER.info("Token: %s", self._token)
        except Exception:
            raise CannotConnect
        else:
            if as_dict:
                return {"token": self._token}
            else:
                return self._token

    def get_mosque_list(self):
        """Fetch mosque list in close proximity."""
        try:
            self._mosque_list = self._mw_connect.all_mosques_neighberhood()
        except Exception:
            raise CannotConnect
        else:
            return self._mosque_list

    def get_prayer_times(self):
        """Fetch prayer times for specific mosque."""
        try:
            self._prayer_times = self._mw_connect.fetch_prayer_times()
        except Exception:
            raise CannotConnect
        else:
            return self._prayer_times


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
