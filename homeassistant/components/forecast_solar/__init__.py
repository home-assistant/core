"""The Forecast.Solar integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import random

from aiohttp import ClientResponseError
import async_timeout
from forecast_solar import (
    Estimate,
    ForecastSolar,
    ForecastSolarError,
    ForecastSolarRatelimit,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Forecast.Solar from a config entry."""
    # Our option flow may cause it to be an empty string,
    # this if statement is here to catch that.
    api_key = entry.options.get(CONF_API_KEY) or None

    if (
        inverter_size := entry.options.get(CONF_INVERTER_SIZE)
    ) is not None and inverter_size > 0:
        inverter_size = inverter_size / 1000

    session = async_get_clientsession(hass)
    forecast = ForecastSolar(
        api_key=api_key,
        session=session,
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
        declination=entry.options[CONF_DECLINATION],
        azimuth=(entry.options[CONF_AZIMUTH] - 180),
        kwp=(entry.options[CONF_MODULES_POWER] / 1000),
        damping=entry.options.get(CONF_DAMPING, 0),
        inverter=inverter_size,
    )

    # Free account have a resolution of 1 hour, using that as the default
    # update interval. Using a higher value for accounts with an API key.
    update_interval = timedelta(hours=1)
    if api_key is not None:
        update_interval = timedelta(minutes=30)

    coordinator: DataUpdateCoordinator[Estimate] = UpdateCoordinator(
        hass, logging.getLogger(__name__), forecast, update_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


class UpdateCoordinator(DataUpdateCoordinator[Estimate]):
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
        self.api_update_interval: timedelta = api_interval
        self.next_scheduled_api_query: datetime | None = None
        self.last_api_update_success: datetime | None = None

    async def update(self) -> Estimate:
        """Fetch new data from API if within rate limit and update sensor values if needed."""

        now = datetime.now(tz=dt.get_time_zone(self.hass.config.time_zone))
        estimate = self.data
        update_error = None
        # Update the estimate from the API if within rate limit
        if (
            self.next_scheduled_api_query is None
            or now >= self.next_scheduled_api_query
        ):
            async with async_timeout.timeout(10):
                _LOGGER.debug("Querying forecast.solar API")
                try:
                    estimate = await self.api.estimate()
                    self.last_api_update_success = now
                except ForecastSolarRatelimit as error:
                    # We hit a rate limit, be more cautious
                    _LOGGER.info("Hit rate limit on forecast.solar API")
                    update_error = error
                except (
                    ForecastSolarError,
                    ClientResponseError,
                    asyncio.TimeoutError,
                ) as error:
                    _LOGGER.warning(
                        "Failed to query forecast.solar API, using cached values. Reason: %s",
                        error,
                    )
                    update_error = error

            # Delay the next update by a small random offset to even out the load on the API
            self.next_scheduled_api_query = (
                now
                + self.api_update_interval
                + timedelta(seconds=random.randint(0, 60))
            )

        # If values are stale for too long, report an error
        # This most likely happens if the internet connection drops or forecast.solar has an outage
        # Note: This could also happen when the integration is loaded initially, which would lead to
        # reloading the integration and potentially failing again?
        if self.last_api_update_success is None or (
            now - self.last_api_update_success
        ) > timedelta(hours=6):
            raise UpdateFailed(update_error)

        # Find the next change point in the reported estimates
        # Replace microsecond = 0 to match the behaviour of HA scheduling -- otherwise, we might
        # unnecessarily run at xx:59:59.yyy
        now = datetime.now(tz=dt.get_time_zone(self.hass.config.time_zone)).replace(
            microsecond=0
        )
        next_value_update = min(
            (timestamp for timestamp in estimate.watts.keys() if timestamp > now),
            default=now + timedelta(minutes=1),
        )

        # Run this method again when the next interesting thing happens (either update API or
        # update sensor values)
        next_update_interval = (
            min(self.next_scheduled_api_query, next_value_update) - now
        )
        # Safeguard to rate-limit calls to this method
        if next_update_interval < timedelta(seconds=1):
            next_update_interval = timedelta(seconds=1)
        _LOGGER.debug(
            "Next estimate value change is at %s, next API query at %s, scheduling next update in %s",
            next_value_update.astimezone(now.tzinfo),
            self.next_scheduled_api_query,
            next_update_interval,
        )

        self.update_interval = next_update_interval
        return estimate
