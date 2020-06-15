"""Common Met Office Data class used by both sensor and entity."""

import logging

import datapoint

from homeassistant.util import utcnow

_LOGGER = logging.getLogger(__name__)


def make_api_mode(mode: str) -> str:
    """Convert human-friendly update mode into API-compatible token."""
    return mode.replace(" ", "").lower()


class MetOfficeData:
    """Get current and forecast data from Datapoint.

    Please note that the 'datapoint' library is not asyncio-friendly, so some
    calls have had to be wrapped with the standard homeassistant helper
    async_add_executor_job, which is why it has to store a 'hass' object.
    """

    def __init__(self, hass, api_key, latitude, longitude, mode):
        """Initialize the data object."""
        self._hass = hass
        self._datapoint = datapoint.connection(api_key=api_key)

        # Public attributes
        self.latitude = latitude
        self.longitude = longitude

        # Private attributes, as they drive the data retrieval
        self._mode = make_api_mode(mode)
        self._datapoint = datapoint.connection(api_key=api_key)
        self._site = None

        # Holds the most recent data from the Met Office
        self.site_id = None
        self.site_name = None
        self.now = None
        self.all = None

    @property
    def mode(self):
        """Return the stored API retrieval mode value."""
        return self._mode

    @mode.setter
    def mode(self, new_mode):
        """Update the mode for retrieving data from DataPoint."""
        new_api_mode = make_api_mode(new_mode)
        if self._mode != new_api_mode:
            self._mode = new_api_mode
            self.now = None
            self.all = None

    async def async_update_site(self):
        """Async wrapper for getting the DataPoint site."""
        return await self._hass.async_add_executor_job(self._update_site)

    def _update_site(self):
        """Return the stored DataPoint Site (will retrieve an updated one if the latitude/longitude have been updated)."""
        try:
            new_site = self._datapoint.get_nearest_forecast_site(
                latitude=self.latitude, longitude=self.longitude
            )
            if self._site is None or self._site.id != new_site.id:
                self._site = new_site
                self.now = None
                self.all = None

            self.site_id = self._site.id
            self.site_name = self._site.name

        except datapoint.exceptions.APIException as err:
            _LOGGER.error("Received error from Met Office Datapoint: %s", err)
            self._site = None
            self.site_id = None
            self.site_name = None
            self.now = None
            self.all = None

        return self._site

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from DataPoint."""
        if self.site_id is None:
            _LOGGER.error("No Met Office forecast site held, check logs for problems")
            return

        try:
            time_now = utcnow()

            forecast = self._datapoint.get_forecast_for_site(self.site_id, self._mode)
            self.now = forecast.now()
            self.all = [
                timestep
                for day in forecast.days
                for timestep in day.timesteps
                if timestep.date > time_now
            ]

        except (ValueError, datapoint.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office connection: %s", err.args)
            self.now = None
            self.all = None
