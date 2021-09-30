"""Helpers used for Met Office integration."""

import logging

import datapoint

from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import utcnow

from .data import MetOfficeData

_LOGGER = logging.getLogger(__name__)


def fetch_site(connection: datapoint.Manager, latitude, longitude):
    """Fetch site information from Datapoint API."""
    try:
        return connection.get_nearest_forecast_site(
            latitude=latitude, longitude=longitude
        )
    except datapoint.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return None


def fetch_data(connection: datapoint.Manager, site, mode) -> MetOfficeData:
    """Fetch weather and forecast from Datapoint API."""
    try:
        forecast = connection.get_forecast_for_site(site.id, mode)
    except (ValueError, datapoint.exceptions.APIException) as err:
        _LOGGER.error("Check Met Office connection: %s", err.args)
        raise UpdateFailed from err
    else:
        time_now = utcnow()
        return MetOfficeData(
            forecast.now(),
            [
                timestep
                for day in forecast.days
                for timestep in day.timesteps
                if timestep.date > time_now
            ],
            site,
        )
