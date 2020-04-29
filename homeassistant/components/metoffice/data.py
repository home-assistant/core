"""Common Met Office Data class used by both sensor and entity."""

from datetime import timedelta
import logging

import datapoint

from homeassistant.util import Throttle

from .const import MODE_3HOURLY

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=35)


class MetOfficeData:
    """Get current and forecast data from Datapoint."""

    def __init__(self, api_key, latitude, longitude):
        """Initialize the data object."""
        self._latitude = latitude
        self._longitude = longitude

        self._refresh_site = True
        self._datapoint = datapoint.connection(api_key=api_key)
        self._site = None

        # Holds the current weather data from the Met Office
        self.now = None

    @property
    def latitude(self):
        """Return the stored latitude value."""
        return self._latitude

    @latitude.setter
    def latitude(self, latitude):
        """Update the stored latitude value and flag the DataPoint Site for a possible refresh."""
        if self._latitude != latitude:
            self._latitude = latitude
            self._refresh_site = True

    @property
    def longitude(self):
        """Return the stored longitude value."""
        return self._longitude

    @longitude.setter
    def longitude(self, longitude):
        """Update the stored longitude value and flag the DataPoint Site for a possible refresh."""
        if self._longitude != longitude:
            self._longitude = longitude
            self._refresh_site = True

    @property
    def site(self):
        """Return the stored DataPoint Site (will retrieve an updated one if the latitude/longitude have been updated)."""
        if self._refresh_site:
            try:
                new_site = self._datapoint.get_nearest_site(
                    latitude=self._latitude, longitude=self._longitude
                )
                if self._site is None or self._site.id != new_site.id:
                    self._site = new_site
                self._refresh_site = False
            except datapoint.exceptions.APIException as err:
                _LOGGER.error("Received error from Met Office Datapoint: %s", err)
                self._site = None
                self.now = None

        return self._site

    @Throttle(DEFAULT_SCAN_INTERVAL)
    def update(self):
        """Get the latest data from DataPoint."""
        if self.site is None:
            _LOGGER.error("No Met Office forecast site held, check logs for problems")
            return

        try:
            forecast = self._datapoint.get_forecast_for_site(self.site.id, MODE_3HOURLY)
            self.now = forecast.now()
        except (ValueError, datapoint.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self.now = None
