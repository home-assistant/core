"""The Forecast.Solar integration."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

import async_timeout
from aiohttp import ClientResponseError
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

from .const import (
    LOGGER,
    DOMAIN
)


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
        # TODO In case there are multiple instances, they should share the api_interval
        self.api_update_interval: timedelta = api_interval
        self.current_api_estimate: Estimate | None = None
        self.last_api_error: Exception | None = None
        self.last_api_success_time: datetime | None = None
        self.next_api_query_time: datetime | None = None
        self.next_value_update_time: datetime | None = None

    async def update(self) -> Estimate:
        """Fetch new data from API if within rate limit and update sensor values if needed."""

        now = datetime.now(tz=dt.get_time_zone(self.hass.config.time_zone))

        # Update the estimate from the API if within rate limit
        if self.next_api_query_time is None or now >= self.next_api_query_time:
            LOGGER.debug("Querying forecast.solar API")
            try:
                async with async_timeout.timeout(10):
                    self.current_api_estimate = await self.api.estimate()
                self.last_api_success_time = now
            except ForecastSolarRatelimit as error:
                # We hit a rate limit, be more cautious
                LOGGER.info("Hit rate limit on forecast.solar API")
                self.last_api_error = error
            except (ForecastSolarConnectionError, asyncio.TimeoutError) as error:
                LOGGER.warning(
                    "Failed to connect to forecast.solar API, using cached values. Reason: %s",
                    error,
                )
                # Try again sooner
                self.next_api_query_time = now + timedelta(minutes=2)
                self.last_api_error = error
            except (ForecastSolarError, ClientResponseError) as error:
                LOGGER.warning(
                    "Failed to query forecast.solar API, using cached values. Reason: %s",
                    error,
                )
                self.last_api_error = error

            # Change the next update by a small random offset to even out the load on the API
            # Since we delay updates until roughly before the value changes, it is ok to subtract
            # a small random time here
            now = datetime.now(tz=dt.get_time_zone(self.hass.config.time_zone))
            self.next_api_query_time = (
                    now
                    + self.api_update_interval
                    - timedelta(seconds=random.randint(0, 120))
            )

        # If values are stale for too long, report an error
        # This most likely happens if the internet connection drops or forecast.solar has an outage
        # Note: This could also happen when the integration is loaded initially, which would lead to
        # reloading the integration and potentially failing again?
        if self.last_api_success_time is None or (
                now - self.last_api_success_time > timedelta(hours=6)
        ):
            raise UpdateFailed(self.last_api_error)

        # self.last_api_update_success is not None here
        assert self.current_api_estimate is not None

        # Update the reported values only if we are at a "value change time", otherwise changes
        # in the values reported by the API lead to a change of values during the hour
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

            # Delay querying right before the value change to have the most recent values +
            # some randomness to not overload the API -- but only if the last success is recent
            if now - self.last_api_success_time < timedelta(
                    hours=1
            ) and self.next_api_query_time < self.next_value_update_time - timedelta(
                seconds=300
            ):
                LOGGER.debug(
                    "Delaying next API query to align with value update at %s",
                    self.next_value_update_time,
                )
                self.next_api_query_time = self.next_value_update_time - timedelta(
                    seconds=random.randint(60, 300)
                )
        else:
            # Have not reached a "value change time", keep the old values
            current_estimate = self.data

        # Run this method again when the next interesting thing happens (either query the API or
        # update sensor values). Replace microsecond = 0 to match the behaviour of HA scheduling,
        # otherwise, we might run at times like xx:59:59.yyy
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
