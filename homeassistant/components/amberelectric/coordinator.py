"""Amber Electric Coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import amberelectric
from amberelectric.models.actual_interval import ActualInterval
from amberelectric.models.channel import ChannelType
from amberelectric.models.current_interval import CurrentInterval
from amberelectric.models.forecast_interval import ForecastInterval
from amberelectric.models.price_descriptor import PriceDescriptor
from amberelectric.rest import ApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

type AmberConfigEntry = ConfigEntry[AmberUpdateCoordinator]


def format_cents_to_dollars(cents: float) -> float:
    """Return a formatted conversion from cents to dollars."""
    return round(cents / 100, 2)

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


def normalize_descriptor(descriptor: PriceDescriptor | None) -> str | None:
    """Return the snake case versions of descriptor names. Returns None if the name is not recognized."""
    if descriptor is None:
        return None
    if descriptor.value == "spike":
        return "spike"
    if descriptor.value == "high":
        return "high"
    if descriptor.value == "neutral":
        return "neutral"
    if descriptor.value == "low":
        return "low"
    if descriptor.value == "veryLow":
        return "very_low"
    if descriptor.value == "extremelyLow":
        return "extremely_low"
    if descriptor.value == "negative":
        return "negative"
    return None


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
            update_interval=timedelta(minutes=1),
        )
        self._api = api
        self.site_id = site_id

    def get_forecasts(self):
        """Return an array of forecasts"""
        results = []
        intervals = self.data["forecasts"]["general"]
        for interval in intervals:
            datum = {}
            datum["duration"] = interval.duration
            datum["date"] = interval.var_date.isoformat()
            datum["nem_date"] = interval.nem_time.isoformat()
            datum["per_kwh"] = format_cents_to_dollars(interval.per_kwh)
            if interval.channel_type == ChannelType.FEEDIN:
                datum["per_kwh"] = datum["per_kwh"] * -1
            datum["spot_per_kwh"] = format_cents_to_dollars(interval.spot_per_kwh)
            datum["start_time"] = interval.start_time.isoformat()
            datum["end_time"] = interval.end_time.isoformat()
            datum["renewables"] = round(interval.renewables)
            datum["spike_status"] = interval.spike_status.value
            datum["descriptor"] = normalize_descriptor(interval.descriptor)

            if interval.range is not None:
                datum["range_min"] = format_cents_to_dollars(interval.range.min)
                datum["range_max"] = format_cents_to_dollars(interval.range.max)
            
            if interval.advanced_price is not None:
                multiplier = -1 if interval.channel_type == ChannelType.FEEDIN else 1
                datum["advanced_price_low"] = multiplier * format_cents_to_dollars(
                    interval.advanced_price.low
                )
                datum["advanced_price_predicted"] = multiplier * format_cents_to_dollars(
                    interval.advanced_price.predicted
                )
                datum["advanced_price_high"] = multiplier * format_cents_to_dollars(
                    interval.advanced_price.high
                )

            results.append(datum)

        return {"forecasts": results}

    def update_price_data(self) -> dict[str, dict[str, Any]]:
        """Update callback."""

        result: dict[str, dict[str, Any]] = {
            "current": {},
            "descriptors": {},
            "forecasts": {},
            "grid": {},
        }
        try:
            data = self._api.get_current_prices(self.site_id, next=288)
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

        LOGGER.debug("Fetched new Amber data: %s", intervals)
        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        return await self.hass.async_add_executor_job(self.update_price_data)
