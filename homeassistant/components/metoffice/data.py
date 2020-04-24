"""Common Met Office Data class used by both sensor and entity."""

from datetime import timedelta
import logging

import datapoint as dp

from homeassistant.util import Throttle

from .const import MODE_3HOURLY

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=35)


class MetOfficeData:
    """Get current and forecast data from Datapoint."""

    def __init__(self, hass, datapoint, site, mode=MODE_3HOURLY):
        """Initialize the data object."""
        self._datapoint = datapoint
        self._site = site
        self._mode = mode
        self.now = None
        self.all = None

    @property
    def site(self):
        """Return the stored DataPoint Site."""
        return self._site

    @site.setter
    def site(self, new_site):
        """Update the store DataPoint Site."""
        if self._site.id != new_site.id:
            self._site = new_site
            self.update()

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from DataPoint."""
        try:
            forecast = self._datapoint.get_forecast_for_site(self.site.id, self.mode)
            self.now = forecast.now()
            self.all = forecast.days
        except (ValueError, dp.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self.now = None
            self.all = None
