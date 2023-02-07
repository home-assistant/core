"""Awattar state management."""

from datetime import datetime
import logging

from awattar_api.awattar_api import AwattarApi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API, DOMAIN, INIT_STATE, UNSUB_OPTIONS_UPDATE_LISTENER

_LOGGER: logging.Logger = logging.getLogger(__name__)


def init_state(url: str) -> dict:
    """Initialize the state with Awattar API."""

    return {API: AwattarApi(url), UNSUB_OPTIONS_UPDATE_LISTENER: {}}


class StateFetcher:
    """
    Representation of the coordinator state handling.

    Whenever the coordinator is triggered, it will call the APIs and update status data.
    """

    coordinator: DataUpdateCoordinator

    def __init__(self, hass: HomeAssistant) -> None:
        """Construct controller with hass property."""
        self._hass: HomeAssistant = hass

    async def fetch_states(self) -> dict:
        """Fetch Awattar forecast via API."""

        _LOGGER.debug("Updating the Awattar coordinator data")

        initial_state = self._hass.data[DOMAIN][INIT_STATE]
        data: dict = self.coordinator.data if self.coordinator.data else {}

        if API in initial_state:
            awattar_api = initial_state[API]
            fetched_forecast: dict = await self._hass.async_add_executor_job(
                awattar_api.get_electricity_price
            )

            forecast_data = []

            for forecast_entry in fetched_forecast["data"]:
                # convert timestamp to human readable date
                forecast_data.append(
                    {
                        "start_time": datetime.utcfromtimestamp(
                            forecast_entry["start_timestamp"] / 1000
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": datetime.utcfromtimestamp(
                            forecast_entry["end_timestamp"] / 1000
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "marketprice": forecast_entry["marketprice"],
                    }
                )

            data["forecast"] = forecast_data
            _LOGGER.debug("Updated the Awattar coordinator data=%s", data)

        return data
