"""Common Met Office Data class used by both sensor and entity."""

import logging

import datapoint

from homeassistant.util import utcnow

from .const import MODE_3HOURLY, MODE_DAILY

_LOGGER = logging.getLogger(__name__)


class MetOfficeData:
    """Get current and forecast data from Datapoint.

    Please note that the 'datapoint' library is not asyncio-friendly, so some
    calls have had to be wrapped with the standard hassio helper
    async_add_executor_job.
    """

    def __init__(self, hass, api_key, latitude, longitude):
        """Initialize the data object."""
        self._hass = hass
        self._datapoint = datapoint.connection(api_key=api_key)
        self._site = None

        # Public attributes
        self.latitude = latitude
        self.longitude = longitude

        # Holds the current data from the Met Office
        self.site_id = None
        self.site_name = None
        self.forecast_3hourly = None
        self.forecast_daily = None
        self.now_3hourly = None
        self.now_daily = None

    async def async_update_site(self):
        """Async wrapper for getting the DataPoint site."""
        return await self._hass.async_add_executor_job(self._update_site)

    def _update_site(self):
        """Determine the nearest DataPoint Site(s) to the held latitude/longitude."""
        try:
            new_site = self._datapoint.get_nearest_forecast_site(
                latitude=self.latitude, longitude=self.longitude
            )
            if self._site is None or self._site.id != new_site.id:
                self._site = new_site
                self.forecast_3hourly = None
                self.forecast_daily = None
                self.now_3hourly = None
                self.now_daily = None

            self.site_id = self._site.id
            self.site_name = self._site.name

        except datapoint.exceptions.APIException as err:
            _LOGGER.error("Received error from Met Office Datapoint: %s", err)
            self._site = None
            self.site_id = None
            self.site_name = None
            self.forecast_3hourly = None
            self.forecast_daily = None
            self.now_3hourly = None
            self.now_daily = None

        return self._site is not None

    async def async_update_hourly(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update_hourly)

    async def async_update_daily(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update_daily)

    def _update_hourly(self):
        """Get the latest hourly data from DataPoint."""
        if self._site is None:
            _LOGGER.error("No Met Office sites held, check logs for problems")
            return
        try:
            forecast_3hourly = self._datapoint.get_forecast_for_site(
                self._site.id, MODE_3HOURLY
            )
        except (ValueError, datapoint.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office connection: %s", err.args)
            self.forecast_3hourly = None
            self.now_3hourly = None
        else:
            self.now_3hourly = forecast_3hourly.now()
            time_now = utcnow()
            self.forecast_3hourly = [
                timestep
                for day in forecast_3hourly.days
                for timestep in day.timesteps
                if timestep.date > time_now
            ]

    def _update_daily(self):
        """Get the latest daily data from DataPoint."""
        if self._site is None:
            _LOGGER.error("No Met Office sites held, check logs for problems")
            return
        try:
            forecast_daily = self._datapoint.get_forecast_for_site(
                self._site.id, MODE_DAILY
            )
        except (ValueError, datapoint.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office connection: %s", err.args)
            self.forecast_daily = None
            self.now_daily = None
        else:
            self.now_daily = forecast_daily.now()
            time_now = utcnow()
            self.forecast_daily = [
                timestep
                for day in forecast_daily.days
                for timestep in day.timesteps
                if timestep.date > time_now
            ]
