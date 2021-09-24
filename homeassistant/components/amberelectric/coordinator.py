"""Amber Electric Coordinator."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from amberelectric import ApiException
from amberelectric.api import amber_api
from amberelectric.model.actual_interval import ActualInterval
from amberelectric.model.channel import ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.forecast_interval import ForecastInterval

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


def is_current(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is a CurrentInterval."""
    return interval.__class__ == CurrentInterval


def is_forecast(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is a ForecastInterval."""
    return interval.__class__ == ForecastInterval


def is_general(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is on the general channel."""
    return interval.channel_type == ChannelType.GENERAL


def is_controlled_load(
    interval: ActualInterval | CurrentInterval | ForecastInterval,
) -> bool:
    """Return true if the supplied interval is on the controlled load channel."""
    return interval.channel_type == ChannelType.CONTROLLED_LOAD


def is_feed_in(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is on the feed in channel."""
    return interval.channel_type == ChannelType.FEED_IN


def first(
    intervals: ActualInterval | CurrentInterval | ForecastInterval,
) -> ActualInterval | CurrentInterval | ForecastInterval | None:
    """Return the first element if it exists, otherwise return None."""
    if len(intervals) > 0:
        return intervals[0]
    return None


class AmberUpdateCoordinator(DataUpdateCoordinator):
    """AmberUpdateCoordinator - In charge of downloading the data for a site, which all the sensors read."""

    def __init__(
        self, hass: HomeAssistant, api: amber_api.AmberApi, site_id: str
    ) -> None:
        """Initialise the data service."""
        super().__init__(
            hass,
            LOGGER,
            name="amberelectric",
            update_method=self.async_update_data,
            update_interval=timedelta(minutes=1),
        )
        self._api = api
        self._site_id = site_id

    def update(self) -> dict[str, Any]:
        """Update callback."""
        try:
            result: dict[str, Any] = {}
            data = self._api.get_current_price(self._site_id, next=48)
            result["prices:current"] = {
                ChannelType.GENERAL: None,
                ChannelType.CONTROLLED_LOAD: None,
                ChannelType.FEED_IN: None,
            }

            result["prices:forecasts"] = {
                ChannelType.GENERAL: [],
                ChannelType.CONTROLLED_LOAD: [],
                ChannelType.FEED_IN: [],
            }
            result["grid:renewables"] = None
            result["status:spike"] = None

            current = [interval for interval in data if is_current(interval)]
            forecasts = [interval for interval in data if is_forecast(interval)]

            general = first([interval for interval in current if is_general(interval)])
            if general is None:
                raise UpdateFailed("No general channel configured")

            result["prices:current"][ChannelType.GENERAL] = general

            result["prices:current"][ChannelType.CONTROLLED_LOAD] = first(
                [interval for interval in current if is_controlled_load(interval)]
            )

            result["prices:current"][ChannelType.FEED_IN] = first(
                [interval for interval in current if is_feed_in(interval)]
            )

            result["prices:forecasts"][ChannelType.GENERAL] = [
                interval for interval in forecasts if is_general(interval)
            ]

            result["prices:forecasts"][ChannelType.CONTROLLED_LOAD] = [
                interval for interval in forecasts if is_controlled_load(interval)
            ]

            result["prices:forecasts"][ChannelType.FEED_IN] = [
                interval for interval in forecasts if is_feed_in(interval)
            ]

            result["grid:renewables"] = general.renewables
            result["status:spike"] = general.spike_status

            LOGGER.debug("Fetched new Amber data: %s", data)
            return result

        except ApiException as api_exception:
            raise UpdateFailed("Missing price data, skipping update") from api_exception

    async def async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        return await self.hass.async_add_executor_job(self.update)
