"""The Awattar coordinator."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API, DOMAIN, INIT_STATE

_LOGGER: logging.Logger = logging.getLogger(__name__)


class AwattarCoordinator(DataUpdateCoordinator):
    """Coordinator is responsible for querying the device at a specified route."""

    def __init__(
        self,
        hass: HomeAssistant,
        scan_interval: timedelta,
    ) -> None:
        """Initialise a custom coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )

    def timestamp_to_date_string(self, timestamp: float) -> str:
        """Convert timestamp to a date time string."""
        return datetime.utcfromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")

    async def _async_update_data(self) -> dict:
        """Fetch Awattar forecast via API."""
        initial_state = self.hass.data[DOMAIN][INIT_STATE]
        data: dict = {}

        if API in initial_state:
            awattar_api = initial_state[API]
            fetched_forecast: dict = await self.hass.async_add_executor_job(
                awattar_api.get_electricity_price
            )

            forecast_data = []

            for forecast_entry in fetched_forecast["data"]:
                forecast_data.append(
                    {
                        "start_time": self.timestamp_to_date_string(
                            forecast_entry["start_timestamp"]
                        ),
                        "end_time": self.timestamp_to_date_string(
                            forecast_entry["end_timestamp"]
                        ),
                        "marketprice": forecast_entry["marketprice"],
                    }
                )

            data["forecast"] = forecast_data

        return data
