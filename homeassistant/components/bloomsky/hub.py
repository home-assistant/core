"""Support for BloomSky weather station."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging

import requests

from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

# The BloomSky only updates every 5-8 minutes as per the API spec so there's
# no point in polling the API more frequently
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)


class BloomSky:
    """Handle all communication with the BloomSky API."""

    # API documentation at http://weatherlution.com/bloomsky-api/
    API_URL = "http://api.bloomsky.com/api/skydata"

    def __init__(self, api_key, is_metric):
        """Initialize the BookSky."""
        self._api_key = api_key
        self._endpoint_argument = "unit=intl" if is_metric else ""
        self.devices = {}
        self.is_metric = is_metric
        _LOGGER.debug("Initial BloomSky device load")
        self.refresh_devices()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_devices(self):
        """Use the API to retrieve a list of devices."""
        _LOGGER.debug("Fetching BloomSky update")
        response = requests.get(
            f"{self.API_URL}?{self._endpoint_argument}",
            headers={"Authorization": self._api_key},
            timeout=10,
        )
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise RuntimeError("Invalid API_KEY")
        if response.status_code == HTTPStatus.METHOD_NOT_ALLOWED:
            _LOGGER.error("You have no bloomsky devices configured")
            return
        if response.status_code != HTTPStatus.OK:
            _LOGGER.error("Invalid HTTP response: %s", response.status_code)
            return
        # Create dictionary keyed off of the device unique id
        self.devices.update({device["DeviceID"]: device for device in response.json()})
