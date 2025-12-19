"""Amber Electric Coordinator."""

from __future__ import annotations

from asyncio import TimerHandle
from datetime import datetime
from random import randint
from typing import Any

import amberelectric
from amberelectric.models.actual_interval import ActualInterval
from amberelectric.models.channel import ChannelType
from amberelectric.models.current_interval import CurrentInterval
from amberelectric.models.forecast_interval import ForecastInterval
from amberelectric.rest import ApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    ESTIMATE_REFRESH_DELAY,
    ESTIMATE_REFRESH_JITTER,
    LOGGER,
    MINUTE_ALIGNED_REFRESH_DELAY,
    MINUTE_ALIGNED_REFRESH_JITTER,
    REQUEST_TIMEOUT,
)
from .helpers import normalize_descriptor

type AmberConfigEntry = ConfigEntry[AmberUpdateCoordinator]


def is_current(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is a CurrentInterval."""
    return isinstance(interval, CurrentInterval)


def is_forecast(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is a ForecastInterval."""
    return isinstance(interval, ForecastInterval)


def is_general(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is on the general channel."""
    return interval.channel_type == ChannelType.GENERAL


def is_controlled_load(
    interval: ActualInterval | CurrentInterval | ForecastInterval,
) -> bool:
    """Return true if the supplied interval is on the controlled load channel."""
    return interval.channel_type == ChannelType.CONTROLLEDLOAD


def is_feed_in(interval: ActualInterval | CurrentInterval | ForecastInterval) -> bool:
    """Return true if the supplied interval is on the feed in channel."""
    return interval.channel_type == ChannelType.FEEDIN


class AmberUpdateCoordinator(DataUpdateCoordinator):
    """AmberUpdateCoordinator - In charge of downloading the data for a site, which all the sensors read."""

    config_entry: AmberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AmberConfigEntry,
        api: amberelectric.AmberApi,
        site_id: str,
    ) -> None:
        """Initialise the data service."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="amberelectric",
            update_interval=None,
        )
        self._api = api
        self.site_id = site_id
        self._eager_refresh_handle: TimerHandle | None = None

    async def _async_setup(self) -> None:
        """Set up coordinator resources."""
        if self.config_entry and not self.config_entry.pref_disable_polling:
            self.config_entry.async_on_unload(
                async_track_utc_time_change(
                    self.hass,
                    self._handle_minute_tick,
                    second=0,
                )
            )

    @callback
    def _handle_minute_tick(self, _: datetime) -> None:
        """Refresh the coordinator on minute boundaries."""
        if not self.config_entry:
            return

        # Cancel any pending eager refreshes
        if self._eager_refresh_handle is not None:
            self._eager_refresh_handle.cancel()
            self._eager_refresh_handle = None

        # Add jitter to reduce request bursts against the Amber API.
        delay = randint(
            max(0, MINUTE_ALIGNED_REFRESH_DELAY - MINUTE_ALIGNED_REFRESH_JITTER),
            MINUTE_ALIGNED_REFRESH_DELAY + MINUTE_ALIGNED_REFRESH_JITTER,
        )

        @callback
        def _do_refresh() -> None:
            if not self.config_entry:
                return
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                name=f"{DOMAIN} - {self.config_entry.title} - refresh",
                eager_start=True,
            )

        self.hass.loop.call_later(delay, _do_refresh)

    @callback
    def _schedule_eager_refresh(self) -> None:
        """Schedule a refresh after a short jitter while estimates are present."""
        delay = randint(
            max(0, ESTIMATE_REFRESH_DELAY - ESTIMATE_REFRESH_JITTER),
            ESTIMATE_REFRESH_DELAY + ESTIMATE_REFRESH_JITTER,
        )
        LOGGER.debug(
            "Scheduled refresh in %s seconds due to estimate pricing for current interval",
            delay,
        )

        @callback
        def _do_refresh() -> None:
            self._eager_refresh_handle = None
            if not self.config_entry or self.hass.is_stopping:
                return
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                name=f"{DOMAIN} - {self.config_entry.title} - estimate refresh",
                eager_start=True,
            )

        self._eager_refresh_handle = self.hass.loop.call_later(delay, _do_refresh)

    def _has_estimate(self, data: dict[str, Any]) -> bool:
        """Return true when current data contains estimated prices."""
        current = data.get("current", {})
        general = current.get("general")
        feed_in = current.get("feed_in")
        return any(
            interval is not None and interval.estimate
            for interval in (general, feed_in)
        )

    def update_price_data(self) -> dict[str, dict[str, Any]]:
        """Update callback."""
        LOGGER.debug("Fetching Amber data")
        result: dict[str, dict[str, Any]] = {
            "current": {},
            "descriptors": {},
            "forecasts": {},
            "grid": {},
        }
        try:
            data = self._api.get_current_prices(
                self.site_id,
                next=288,
                _request_timeout=REQUEST_TIMEOUT,
            )
            intervals = [interval.actual_instance for interval in data]
        except ApiException as api_exception:
            raise UpdateFailed("Missing price data, skipping update") from api_exception

        current = [interval for interval in intervals if is_current(interval)]
        forecasts = [interval for interval in intervals if is_forecast(interval)]
        general = [interval for interval in current if is_general(interval)]

        if len(general) == 0:
            raise UpdateFailed("No general channel configured")

        result["current"]["general"] = general[0]
        result["descriptors"]["general"] = normalize_descriptor(general[0].descriptor)
        result["forecasts"]["general"] = [
            interval for interval in forecasts if is_general(interval)
        ]
        result["grid"]["renewables"] = round(general[0].renewables)
        result["grid"]["price_spike"] = general[0].spike_status.value
        tariff_information = general[0].tariff_information
        if tariff_information:
            result["grid"]["demand_window"] = tariff_information.demand_window

        controlled_load = [
            interval for interval in current if is_controlled_load(interval)
        ]
        if controlled_load:
            result["current"]["controlled_load"] = controlled_load[0]
            result["descriptors"]["controlled_load"] = normalize_descriptor(
                controlled_load[0].descriptor
            )
            result["forecasts"]["controlled_load"] = [
                interval for interval in forecasts if is_controlled_load(interval)
            ]

        feed_in = [interval for interval in current if is_feed_in(interval)]
        if feed_in:
            result["current"]["feed_in"] = feed_in[0]
            result["descriptors"]["feed_in"] = normalize_descriptor(
                feed_in[0].descriptor
            )
            result["forecasts"]["feed_in"] = [
                interval for interval in forecasts if is_feed_in(interval)
            ]

        LOGGER.debug(
            "Fetched new Amber data: %s",
            intervals[0] if intervals else None,
        )
        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        data = await self.hass.async_add_executor_job(self.update_price_data)

        if self._has_estimate(data):
            self._schedule_eager_refresh()

        return data

    async def async_shutdown(self) -> None:
        """Cancel pending refreshes and shut down the coordinator."""
        if self._eager_refresh_handle is not None:
            self._eager_refresh_handle.cancel()
            self._eager_refresh_handle = None
        await super().async_shutdown()
