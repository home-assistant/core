from datetime import datetime, timedelta
from typing import List, Union

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


def is_current(
    interval: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> bool:
    return interval.__class__ == CurrentInterval


def is_forecast(
    interval: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> bool:
    return interval.__class__ == ForecastInterval


def is_general(
    interval: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> bool:
    return interval.channel_type == ChannelType.GENERAL


def is_controlled_load(
    interval: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> bool:
    return interval.channel_type == ChannelType.CONTROLLED_LOAD


def is_feed_in(
    interval: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> bool:
    return interval.channel_type == ChannelType.FEED_IN


def first(
    intervals: Union[ActualInterval, CurrentInterval, ForecastInterval]
) -> Union[ActualInterval, CurrentInterval, ForecastInterval, None]:
    if len(intervals) > 0:
        return intervals[0]
    else:
        return None


class AmberDataService:
    def __init__(self, hass: HomeAssistant, api: amber_api.AmberApi, site_id: str):
        self._hass = hass
        self._api = api
        self._site_id = site_id
        self.coordinator: Union[DataUpdateCoordinator, None] = None

        self.data: List[Union[ActualInterval, CurrentInterval, ForecastInterval]]

        self.site: Union[Site, None] = None
        self.current_prices: dict[str, Union[CurrentInterval, None]] = {
            ChannelType.GENERAL: None,
            ChannelType.CONTROLLED_LOAD: None,
            ChannelType.FEED_IN: None,
        }

        self.forecasts: dict[str, Union[List[ForecastInterval], None]] = {
            ChannelType.GENERAL: None,
            ChannelType.CONTROLLED_LOAD: None,
            ChannelType.FEED_IN: None,
        }

    @callback
    def async_setup(self) -> None:
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name="amberelectric",
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    def update_interval(self) -> timedelta:
        return timedelta(minutes=1)

    def update(self) -> None:
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

        try:
            sites = list(
                filter(lambda site: site.id == self._site_id, self._api.get_sites())
            )
            if len(sites) > 0:
                self.site = sites[0]

            start_date = (datetime.today() - timedelta(hours=12, minutes=0)).date()
            end_date = (datetime.today() + timedelta(hours=12, minutes=0)).date()

            self.data = self._api.get_prices(
                self._site_id, start_date=start_date, end_date=end_date
            )

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

            self.forecasts[ChannelType.GENERAL] = list(filter(is_general, forecasts))[
                0:23
            ]
            self.forecasts[ChannelType.CONTROLLED_LOAD] = list(
                filter(is_controlled_load, forecasts)
            )[0:23]
            self.forecasts[ChannelType.FEED_IN] = list(filter(is_feed_in, forecasts))[
                0:23
            ]

            LOGGER.debug("Fetched new Amber data: %s", self.data)

        except ApiException as e:
            raise UpdateFailed("Missing price data, skipping update") from e

    async def async_update_data(self) -> None:
        await self._hass.async_add_executor_job(self.update)
