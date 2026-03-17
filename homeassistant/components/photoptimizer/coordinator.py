"""Photoptimizer coordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from forecast_solar import ForecastSolar, ForecastSolarError

from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_EFFICIENCY_ROUND_TRIP,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_RESERVE_PERCENT,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_EMHASS_TOKEN,
    CONF_EMHASS_URL,
    CONF_HORIZON_HOURS,
    CONF_LOAD_FORECAST_ENTITY,
    CONF_PV_FORECAST_ENTITY,
    CONF_TIMEZONE,
    CONF_WEAR_COST_PER_KWH,
    DEFAULT_BATTERY_EFFICIENCY_ROUND_TRIP,
    DEFAULT_BATTERY_SOC_RESERVE_PERCENT,
    DEFAULT_EMHASS_URL,
    DEFAULT_HORIZON_HOURS,
    DEFAULT_WEAR_COST_PER_KWH,
)
from .emhass_client import EmhassClient
from .models import OptimizationBucket, OptimizationInputs

_LOGGER = logging.getLogger(__name__)


class PhotoptimizerCoordinator(DataUpdateCoordinator[dict]):
    """Aggregate inputs for EMHASS and expose the combined result."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: ForecastSolar
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="photoptimizer forecast",
            update_interval=timedelta(minutes=30),
            update_method=self._async_update_data,
            config_entry=entry,
        )
        self.client = client
        self.entry = entry
        self.emhass_url = entry.data.get(CONF_EMHASS_URL, DEFAULT_EMHASS_URL)
        self.emhass_token = entry.data.get(CONF_EMHASS_TOKEN)
        self.emhass = EmhassClient(
            hass,
            self.emhass_url,
            self.emhass_token,
            battery_capacity_kwh=float(
                entry.data.get(
                    CONF_BATTERY_CAPACITY_KWH,
                    5.0,
                )
            ),
            battery_efficiency=(
                float(
                    entry.data.get(
                        CONF_BATTERY_EFFICIENCY_ROUND_TRIP,
                        DEFAULT_BATTERY_EFFICIENCY_ROUND_TRIP,
                    )
                )
                / 100.0
            ),
            battery_soc_reserve=(
                entry.data.get(
                    CONF_BATTERY_SOC_RESERVE_PERCENT,
                    DEFAULT_BATTERY_SOC_RESERVE_PERCENT,
                )
                / 100.0
            ),
            wear_cost_per_kwh=entry.data.get(
                CONF_WEAR_COST_PER_KWH,
                DEFAULT_WEAR_COST_PER_KWH,
            ),
        )

    async def _hourly_from_price_entity(
        self, entity_id: str, buckets: list[OptimizationBucket]
    ) -> None:
        state = self.hass.states.get(entity_id)

        if state is None:
            raise UpdateFailed(f"Price entity {entity_id} not found")

        tz_name = self.entry.data.get(CONF_TIMEZONE) or self.hass.config.time_zone
        tz = dt_util.get_time_zone(tz_name) or dt_util.UTC

        bucket_index = {bucket.start: bucket for bucket in buckets}

        for key, value in state.attributes.items():
            if isinstance(value, (int, float)):
                dt = dt_util.parse_datetime(str(key))
                if dt is None:
                    continue
                dt_local = dt_util.as_local(dt).astimezone(tz)
                hour_start = dt_local.replace(minute=0, second=0, microsecond=0)
                if hour_start in bucket_index:
                    bucket_index[hour_start].price = float(value)

        last_price: float | None = None
        for bucket in buckets:
            if bucket.price != 0.0:
                last_price = bucket.price
            elif last_price is not None:
                bucket.price = last_price

    async def _hourly_from_load_entity(
        self, entity_id: str, buckets: list[OptimizationBucket]
    ) -> None:
        state = self.hass.states.get(entity_id)

        if state is None:
            raise UpdateFailed(f"Load entity {entity_id} not found")

        tz_name = self.entry.data.get(CONF_TIMEZONE) or self.hass.config.time_zone
        tz = dt_util.get_time_zone(tz_name) or dt_util.UTC

        bucket_index = {bucket.start: bucket for bucket in buckets}

        for key, value in state.attributes.items():
            if not isinstance(value, (int, float)):
                continue
            dt = dt_util.parse_datetime(str(key))
            if dt is None:
                continue
            dt_local = dt_util.as_local(dt).astimezone(tz)
            hour_start = dt_local.replace(minute=0, second=0, microsecond=0)
            if hour_start in bucket_index:
                bucket_index[hour_start].load = float(value) / 1000.0

        last_load: float | None = None
        for bucket in buckets:
            if bucket.load != 0.0:
                last_load = bucket.load
            elif last_load is not None:
                bucket.load = last_load

    async def _hourly_from_forecast_solar(
        self, buckets: list[OptimizationBucket], raw_pv
    ) -> None:
        tz_name = self.entry.data.get(CONF_TIMEZONE) or self.hass.config.time_zone
        tz = dt_util.get_time_zone(tz_name) or dt_util.UTC

        bucket_index = {bucket.start: bucket for bucket in buckets}

        for dt_utc, wh in raw_pv.wh_period.items():
            dt_local = dt_util.as_local(dt_utc).astimezone(tz)
            hour_start = dt_local.replace(minute=0, second=0, microsecond=0)
            if hour_start in bucket_index:
                bucket_index[hour_start].pv += float(wh) / 1000.0

    async def _hourly_from_pv_entity(
        self, entity_id: str, buckets: list[OptimizationBucket]
    ) -> None:
        """Fill PV from a forecast entity with datetime-keyed attributes."""

        state = self.hass.states.get(entity_id)
        if state is None:
            raise UpdateFailed(f"PV forecast entity {entity_id} not found")

        tz_name = self.entry.data.get(CONF_TIMEZONE) or self.hass.config.time_zone
        tz = dt_util.get_time_zone(tz_name) or dt_util.UTC
        bucket_index = {bucket.start: bucket for bucket in buckets}

        for key, value in state.attributes.items():
            if not isinstance(value, (int, float)):
                continue
            dt = dt_util.parse_datetime(str(key))
            if dt is None:
                continue
            dt_local = dt_util.as_local(dt).astimezone(tz)
            hour_start = dt_local.replace(minute=0, second=0, microsecond=0)
            if hour_start in bucket_index:
                val = float(value)
                if val > 50:
                    val = val / 1000.0
                bucket_index[hour_start].pv = val

    async def _hourly_from_load_profile(
        self, buckets: list[OptimizationBucket], profile: list[float]
    ) -> None:
        """Fill load buckets from a 24-hour profile."""

        for bucket in buckets:
            bucket.load = profile[bucket.start.hour]

    async def _build_load_profile(self, entity_id: str | None) -> list[float]:
        """Build a simple 24h load profile from history; fallback to defaults.

        - Pull hourly statistics for the last 7 days (mean).
        - Average by hour-of-day to get 24 values.
        - Convert W to kWh for 1h buckets; if we get sums, treat them as kWh.
        - Fill gaps with a baked-in default profile.
        """
        default_profile = [
            0.4,
            0.35,
            0.35,
            0.35,
            0.35,
            0.4,
            0.45,
            0.5,
            0.55,
            0.6,
            0.65,
            0.7,
            0.7,
            0.7,
            0.75,
            0.8,
            0.9,
            1.2,
            1.4,
            1.5,
            1.3,
            1.0,
            0.8,
            0.6,
        ]

        if not entity_id:
            return default_profile

        start = dt_util.utcnow() - timedelta(days=7)

        def _get_stats(
            hass: HomeAssistant,
        ) -> dict[str, list[StatisticsRow]]:
            return statistics_during_period(
                hass,
                start,
                None,
                {entity_id},
                "hour",
                None,
                {"mean", "sum"},
            )

        try:
            stats = await self.hass.async_add_executor_job(_get_stats, self.hass)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Load stats query failed: %s", err)
            return default_profile

        rows = stats.get(entity_id) or []
        hourly_totals = [0.0] * 24
        hourly_counts = [0] * 24

        for row in rows:
            start_ts = row.get("start")
            if start_ts is None or not isinstance(start_ts, datetime):
                continue
            hour = dt_util.as_local(start_ts).hour
            # Prefer mean; fall back to sum/state
            value = row.get("mean")
            if value is None:
                value = row.get("sum")
            if value is None:
                value = row.get("state")
            if value is None:
                continue
            # Treat values > 30 as Watts and convert
            val = float(value)
            if val > 30:  # assume W average over the hour
                val = val / 1000.0
            hourly_totals[hour] += val
            hourly_counts[hour] += 1

        profile: list[float] = []
        for hour in range(24):
            if hourly_counts[hour]:
                profile.append(hourly_totals[hour] / hourly_counts[hour])
            else:
                profile.append(default_profile[hour])

        return profile

    def _read_battery_soc(self) -> float:
        """Read and normalize the current battery SOC from Home Assistant."""
        soc_entity = self.entry.data.get(CONF_BATTERY_SOC_ENTITY)
        soc_state = self.hass.states.get(soc_entity) if soc_entity else None
        try:
            soc_value = float(soc_state.state) if soc_state and soc_state.state else 0.0
        except (TypeError, ValueError):
            soc_value = 0.0

        if soc_value > 1:
            soc_value = soc_value / 100.0

        return max(0.0, min(1.0, soc_value))

    def _log_timeline(self, timeline: list[OptimizationBucket]) -> None:
        """Log the aggregated inputs passed into EMHASS."""
        _LOGGER.debug(
            "Photoptimizer inputs (%d hours):\n  %s\n%s",
            len(timeline),
            f"{'Hour':<17} {'Price':>9} {'PV (kWh)':>10} {'Load (kWh)':>11}",
            "\n".join(
                f"  {bucket.start.strftime('%Y-%m-%d %H:%M')} "
                f"{bucket.price:9.4f} "
                f"{bucket.pv:10.3f} "
                f"{bucket.load:11.3f}"
                for bucket in timeline
            ),
        )

    async def _async_update_data(self) -> dict:
        """Fetch forecast data."""
        try:
            async with asyncio.timeout(30):
                timeline: list[OptimizationBucket] = []
                horizon_hours = self.entry.data.get(
                    CONF_HORIZON_HOURS, DEFAULT_HORIZON_HOURS
                )
                tz_name = (
                    self.entry.data.get(CONF_TIMEZONE) or self.hass.config.time_zone
                )
                tz = dt_util.get_time_zone(tz_name) or dt_util.UTC
                now = dt_util.now(tz).replace(minute=0, second=0, microsecond=0)
                for hour_offset in range(horizon_hours):
                    bucket_start = now + timedelta(hours=hour_offset)
                    timeline.append(
                        OptimizationBucket(
                            start=bucket_start,
                            price=0.0,
                            pv=0.0,
                            load=0.0,
                        )
                    )

                price_entity = self.entry.data.get(CONF_ELECTRICITY_PRICE_ENTITY)
                if price_entity:
                    await self._hourly_from_price_entity(price_entity, timeline)

                pv_entity = self.entry.data.get(CONF_PV_FORECAST_ENTITY)
                raw_pv = None
                if pv_entity:
                    await self._hourly_from_pv_entity(pv_entity, timeline)
                else:
                    raw_pv = await self.client.estimate()
                    await self._hourly_from_forecast_solar(timeline, raw_pv)

                load_entity = self.entry.data.get(CONF_LOAD_FORECAST_ENTITY)
                if load_entity:
                    await self._hourly_from_load_entity(load_entity, timeline)
                else:
                    load_profile = await self._build_load_profile(None)
                    await self._hourly_from_load_profile(timeline, load_profile)

                optimization_inputs = OptimizationInputs(
                    timeline=timeline,
                    battery_soc=self._read_battery_soc(),
                    raw_forecast_solar=raw_pv,
                )
                emhass_result = await self.emhass.async_run_naive_mpc(
                    optimization_inputs
                )

                if emhass_result is None:
                    raise UpdateFailed("EMHASS optimization failed")

                result = {
                    "timeline": [bucket.as_dict() for bucket in timeline],
                    "inputs": {"battery_soc": optimization_inputs.battery_soc},
                    "raw": {"forecast_solar": raw_pv},
                    "emhass": emhass_result.as_dict(),
                }

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    self._log_timeline(timeline)

                return result

        except ForecastSolarError as err:
            raise UpdateFailed(f"Forecast.Solar API error: {err}") from err
