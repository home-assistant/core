"""Common Met Office Data class used by both sensor and entity."""

from datetime import timedelta
import logging

import datapoint

from homeassistant.util import Throttle

from .const import MODE_3HOURLY

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=35)


class MetOfficeData:
    """Get current and forecast data from Datapoint."""

    def __init__(self, hass, dpc, position, mode=MODE_3HOURLY):
        """Initialize the data object."""
        self._datapoint = dpc
        self._latitude = self._longitude = None
        self._mode = mode
        self._site = None
        self._now = None
        self._all = None

        # trigger getting the site and data
        self.position = position
        self.update()

    @property
    def position(self):
        """Return the current position being forecast."""
        return (self._latitude, self._longitude)

    @position.setter
    def position(self, position):
        """Update the current position being forecast."""
        new_latitude, new_longitude = position
        if new_latitude != self._latitude or new_longitude != self._longitude:
            self._latitude = new_latitude
            self._longitude = new_longitude

            try:
                new_site = self._datapoint.get_nearest_forecast_site(
                    latitude=self._latitude, longitude=self._longitude,
                )

                if self.site is None or new_site.id != self.site.id:
                    self._site = new_site
            except datapoint.exceptions.APIException as err:
                _LOGGER.error("Received error from Met Office Datapoint: %s", err)
                self._site = None

    @property
    def mode(self):
        """Return the data retrieval mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode):
        """Update the data retrieval mode."""
        if self._mode != new_mode:
            self._mode = new_mode
            self.update()

    @property
    def site(self):
        """Return the stored DataPoint Site."""
        return self._site

    @property
    def now(self):
        """Return the current weather data."""
        if self._now is None:
            self.update()
        return self._now

    @property
    def all(self):
        """Return all the forecast weather data."""
        if self._all is None:
            self.update()
        return self._all

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from DataPoint."""
        try:
            forecast = self._datapoint.get_forecast_for_site(self.site.id, self.mode)
            self._now = forecast.now()
            self._all = forecast.days
        except (ValueError, datapoint.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self._now = None
            self._all = None
