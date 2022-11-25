"""The Forecast.Solar integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from aiohttp import ClientResponseError
import async_timeout
from forecast_solar import (
    Estimate,
    ForecastSolar,
    ForecastSolarConnectionError,
    ForecastSolarError,
    ForecastSolarRatelimit,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import DOMAIN, LOGGER


class ForecastSolarUpdateCoordinator(DataUpdateCoordinator[Estimate]):
    """Update coordinator for Forecast.Solar."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api: ForecastSolar,
        api_interval: timedelta,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
            update_method=self.update,
        )
        self.api = api
        # Note: In case there are multiple instances, they probably should share the api_interval, since the rate-limit
        # is shared, too. However, the limits are quite generous, and you can get away with 6-12 planes
        self.api_update_interval: timedelta = api_interval
        self.current_api_estimate: Estimate | None = None
        self.last_api_error: Exception | None = None
        self.last_api_success_time: datetime | None = None
        self.next_api_query_time: datetime | None = None
        self.next_value_update_time: datetime | None = None

    def _now(self) -> datetime:
        return datetime.now(tz=dt.get_time_zone(self.hass.config.time_zone))

    async def update(self) -> Estimate:
        """Fetch new data from API if within rate limit and update sensor values if needed."""

        # Update the estimate from the API if within rate limit

        if self.next_api_query_time is None or self.next_api_query_time <= self._now():
            LOGGER.debug("Querying forecast.solar API")

            api_error: Exception | None = None
            try:
                async with async_timeout.timeout(10):
                    self.current_api_estimate = await self.api.estimate()
                self.last_api_success_time = self._now()
            except ForecastSolarRatelimit as error:
                LOGGER.info("Hit rate limit on forecast.solar API")
                api_error = error
            except (ForecastSolarConnectionError, asyncio.TimeoutError) as error:
                LOGGER.warning(
                    "Failed to connect to forecast.solar API, using cached values. Reason: %s",
                    error,
                )
                api_error = error
            except (ForecastSolarError, ClientResponseError) as error:
                LOGGER.warning(
                    "Failed to query forecast.solar API, using cached values. Reason: %s",
                    error,
                )
                api_error = error

            # Note: Also sets last_api_error to None if query is successful
            self.last_api_error = api_error
            self.next_api_query_time = self._now() + self.api_update_interval

            # if isinstance(api_error, (ForecastSolarConnectionError, asyncio.TimeoutError)):
            # We couldn't connect, so lets try again sooner
            # self.next_api_query_time = self._now() + timedelta(minutes=2)

        # If values are stale for too long, report an error
        # This most likely happens if the internet connection drops or forecast.solar has an outage
        # Note: This could also happen when the integration is loaded initially, which would lead to
        # reloading the integration and potentially failing again?
        if self.last_api_success_time is None or (
            self._now() - self.last_api_success_time > timedelta(hours=6)
        ):
            raise UpdateFailed(self.last_api_error)
        assert self.current_api_estimate is not None

        # Update the reported values only if we are at a "value change time", otherwise changes
        # in the values reported by the API lead to a change of values during the hour
        now = self._now()
        if self.next_value_update_time is None or now >= self.next_value_update_time:
            current_estimate: Estimate = self.current_api_estimate

            # Find the next change point in the reported estimates
            self.next_value_update_time = min(
                (
                    timestamp
                    for timestamp in current_estimate.watts.keys()
                    if timestamp > now
                ),
                default=now + timedelta(minutes=1),
            ).astimezone(now.tzinfo)
        else:
            # Have not reached a "value change time", keep the old values
            current_estimate = self.data

        # Run this method again when the next interesting thing happens (either query the API or
        # update sensor values). Replace microsecond = 0 to match the behaviour of HA scheduling,
        # otherwise, we might run at times like xx:59:59.yyy
        assert self.next_api_query_time is not None
        next_update_interval = min(
            self.next_api_query_time, self.next_value_update_time
        ) - now.replace(microsecond=0)

        # Safeguard to rate-limit calls to this method
        if next_update_interval < timedelta(seconds=1):
            next_update_interval = timedelta(seconds=1)
        if next_update_interval > timedelta(hours=2):
            next_update_interval = timedelta(hours=2)

        LOGGER.debug(
            "Next estimate value change is at %s, next API query at %s, scheduling next update in %s",
            self.next_value_update_time,
            self.next_api_query_time,
            next_update_interval,
        )

        self.update_interval = next_update_interval
        return current_estimate
