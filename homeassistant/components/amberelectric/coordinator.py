"""Amber Electric Coordinator."""
from __future__ import annotations

from datetime import timedelta

from amberelectric import ApiException
from amberelectric.api import amber_api
from amberelectric.model.actual_interval import ActualInterval
from amberelectric.model.channel import ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.forecast_interval import ForecastInterval
from amberelectric.model.site import Site

from homeassistant.core import HomeAssistant, callback
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


class AmberDataService:
    """AmberDataService - In charge of downloading the data for a site, which all the sensors read."""

    def __init__(
        self, hass: HomeAssistant, api: amber_api.AmberApi, site_id: str
    ) -> None:
        """Initialise the data service."""
        self._hass = hass
        self._api = api
        self._site_id = site_id
        self.coordinator: DataUpdateCoordinator | None = None

        self.data: list[ActualInterval | CurrentInterval | ForecastInterval]

        self.site: Site | None = None
        self.current_prices: dict[str, CurrentInterval | None] = {
            ChannelType.GENERAL: None,
            ChannelType.CONTROLLED_LOAD: None,
            ChannelType.FEED_IN: None,
        }

        self.forecasts: dict[str, list[ForecastInterval] | None] = {
            ChannelType.GENERAL: None,
            ChannelType.CONTROLLED_LOAD: None,
            ChannelType.FEED_IN: None,
        }

    @callback
    def async_setup(self) -> None:
        """Set up the data service."""
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name="amberelectric",
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    def update_interval(self) -> timedelta:
        """Update interval property."""
        return timedelta(minutes=1)

    def update(self) -> None:
        """Update callback."""
        try:
            sites = list(
                filter(lambda site: site.id == self._site_id, self._api.get_sites())
            )
            if len(sites) > 0:
                self.site = sites[0]

            self.data = self._api.get_current_price(self._site_id, next=48)
            self.current_prices = {
                ChannelType.GENERAL: None,
                ChannelType.CONTROLLED_LOAD: None,
                ChannelType.FEED_IN: None,
            }

            self.forecasts = {
                ChannelType.GENERAL: None,
                ChannelType.CONTROLLED_LOAD: None,
                ChannelType.FEED_IN: None,
            }

            current = list(filter(is_current, self.data))
            forecasts = list(filter(is_forecast, self.data))

            self.current_prices[ChannelType.GENERAL] = first(
                list(filter(is_general, current))
            )

            self.current_prices[ChannelType.CONTROLLED_LOAD] = first(
                list(filter(is_controlled_load, current))
            )

            self.current_prices[ChannelType.FEED_IN] = first(
                list(filter(is_feed_in, current))
            )

            self.forecasts[ChannelType.GENERAL] = list(filter(is_general, forecasts))
            self.forecasts[ChannelType.CONTROLLED_LOAD] = list(
                filter(is_controlled_load, forecasts)
            )
            self.forecasts[ChannelType.FEED_IN] = list(filter(is_feed_in, forecasts))

            LOGGER.debug("Fetched new Amber data: %s", self.data)

        except ApiException as api_exception:
            raise UpdateFailed("Missing price data, skipping update") from api_exception

    async def async_update_data(self) -> None:
        """Async update wrapper."""
        await self._hass.async_add_executor_job(self.update)
