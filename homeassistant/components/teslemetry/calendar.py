"""Calendar platform for Teslemetry integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TeslemetryConfigEntry
from .entity import TeslemetryEnergyInfoEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Calendar platform from a config entry."""

    entities_to_add: list[CalendarEntity] = []

    entities_to_add.extend(
        TeslemetryTariffSchedule(energy, "tariff_content_v2")
        for energy in entry.runtime_data.energysites
        if energy.info_coordinator.data.get("tariff_content_v2_seasons")
    )

    entities_to_add.extend(
        TeslemetryTariffSchedule(energy, "tariff_content_v2_sell_tariff")
        for energy in entry.runtime_data.energysites
        if energy.info_coordinator.data.get("tariff_content_v2_sell_tariff_seasons")
    )

    async_add_entities(entities_to_add)


def _is_day_in_range(day_of_week: int, from_day: int, to_day: int) -> bool:
    """Check if a day of week falls within a range, handling week crossing."""
    if from_day <= to_day:
        return from_day <= day_of_week <= to_day
    # Week crossing (e.g., Fri=4 to Mon=0)
    return day_of_week >= from_day or day_of_week <= to_day


def _parse_period_times(
    period_def: dict[str, Any],
    base_day: datetime,
) -> tuple[datetime, datetime] | None:
    """Parse a TOU period definition into start and end times.

    Returns None if the base_day's weekday doesn't match the period's day range.
    For periods crossing midnight, end_time will be on the following day.
    """
    # DaysOfWeek are from 0-6 (Monday-Sunday)
    from_day = period_def.get("fromDayOfWeek", 0)
    to_day = period_def.get("toDayOfWeek", 6)

    if not _is_day_in_range(base_day.weekday(), from_day, to_day):
        return None

    # Hours are from 0-23, so 24 hours is 0-0
    from_hour = period_def.get("fromHour", 0)
    to_hour = period_def.get("toHour", 0)

    # Minutes are from 0-59, so 60 minutes is 0-0
    from_minute = period_def.get("fromMinute", 0)
    to_minute = period_def.get("toMinute", 0)

    start_time = base_day.replace(
        hour=from_hour, minute=from_minute, second=0, microsecond=0
    )
    end_time = base_day.replace(hour=to_hour, minute=to_minute, second=0, microsecond=0)

    if end_time <= start_time:
        end_time += timedelta(days=1)

    return start_time, end_time


def _build_event(
    key_base: str,
    season_name: str,
    period_name: str,
    price: float | None,
    start_time: datetime,
    end_time: datetime,
) -> CalendarEvent:
    """Build a CalendarEvent for a tariff period."""
    price_str = f"{price:.2f}/kWh" if price is not None else "Unknown Price"
    return CalendarEvent(
        start=start_time,
        end=end_time,
        summary=f"{period_name.capitalize().replace('_', ' ')}: {price_str}",
        description=(
            f"Season: {season_name.capitalize()}\n"
            f"Period: {period_name.capitalize().replace('_', ' ')}\n"
            f"Price: {price_str}"
        ),
        uid=f"{key_base}_{season_name}_{period_name}_{start_time.isoformat()}",
    )


class TeslemetryTariffSchedule(TeslemetryEnergyInfoEntity, CalendarEntity):
    """Energy Site Tariff Schedule Calendar."""

    def __init__(
        self,
        data: Any,
        key_base: str,
    ) -> None:
        """Initialize the tariff schedule calendar."""
        self.key_base: str = key_base
        self.seasons: dict[str, dict[str, Any]] = {}
        self.charges: dict[str, dict[str, Any]] = {}
        super().__init__(data, key_base)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current active tariff event."""
        now = dt_util.now()
        current_season_name = self._get_current_season(now)

        if not current_season_name or not self.seasons.get(current_season_name):
            return None

        # Time of use (TOU) periods define the tariff schedule within a season
        tou_periods = self.seasons[current_season_name].get("tou_periods", {})

        for period_name, period_group in tou_periods.items():
            for period_def in period_group.get("periods", []):
                result = _parse_period_times(period_def, now)
                if result is None:
                    continue

                start_time, end_time = result

                # Check if now falls within this period
                if not (start_time <= now < end_time):
                    # For cross-midnight periods, check yesterday's instance
                    start_time -= timedelta(days=1)
                    end_time -= timedelta(days=1)
                    if not (start_time <= now < end_time):
                        continue

                price = self._get_price_for_period(current_season_name, period_name)
                return _build_event(
                    self.key_base,
                    current_season_name,
                    period_name,
                    price,
                    start_time,
                    end_time,
                )

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events (tariff periods) within a datetime range."""
        events: list[CalendarEvent] = []

        start_date = dt_util.as_local(start_date)
        end_date = dt_util.as_local(end_date)

        # Start one day earlier to catch TOU periods that cross midnight
        # from the previous evening into the query range.
        current_day = dt_util.start_of_local_day(start_date) - timedelta(days=1)
        while current_day < end_date:
            season_name = self._get_current_season(current_day)
            if not season_name or not self.seasons.get(season_name):
                current_day += timedelta(days=1)
                continue

            tou_periods = self.seasons[season_name].get("tou_periods", {})

            for period_name, period_group in tou_periods.items():
                for period_def in period_group.get("periods", []):
                    result = _parse_period_times(period_def, current_day)
                    if result is None:
                        continue

                    start_time, end_time = result

                    if start_time < end_date and end_time > start_date:
                        price = self._get_price_for_period(season_name, period_name)
                        events.append(
                            _build_event(
                                self.key_base,
                                season_name,
                                period_name,
                                price,
                                start_time,
                                end_time,
                            )
                        )

            current_day += timedelta(days=1)

        events.sort(key=lambda x: x.start)
        return events

    def _get_current_season(self, date_to_check: datetime) -> str | None:
        """Determine the active season for a given date."""
        local_date = dt_util.as_local(date_to_check)
        year = local_date.year

        for season_name, season_data in self.seasons.items():
            if not season_data:
                continue

            try:
                from_month = season_data["fromMonth"]
                from_day = season_data["fromDay"]
                to_month = season_data["toMonth"]
                to_day = season_data["toDay"]

                # Handle seasons that cross year boundaries
                start_year = year
                end_year = year

                # Season crosses year boundary (e.g., Oct-Mar)
                if from_month > to_month or (
                    from_month == to_month and from_day > to_day
                ):
                    if local_date.month > from_month or (
                        local_date.month == from_month and local_date.day >= from_day
                    ):
                        end_year = year + 1
                    else:
                        start_year = year - 1

                season_start = local_date.replace(
                    year=start_year,
                    month=from_month,
                    day=from_day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                season_end = local_date.replace(
                    year=end_year,
                    month=to_month,
                    day=to_day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                ) + timedelta(days=1)

                if season_start <= local_date < season_end:
                    return season_name
            except KeyError, ValueError:
                continue

        return None

    def _get_price_for_period(self, season_name: str, period_name: str) -> float | None:
        """Get the price for a specific season and period name."""
        try:
            season_charges = self.charges.get(season_name, self.charges.get("ALL", {}))
            rates = season_charges.get("rates", {})
            price = rates.get(period_name, rates.get("ALL"))
            return float(price) if price is not None else None
        except KeyError, ValueError, TypeError:
            return None

    def _async_update_attrs(self) -> None:
        """Update the Calendar attributes from coordinator data."""
        self.seasons = self.coordinator.data.get(f"{self.key_base}_seasons", {})
        self.charges = self.coordinator.data.get(f"{self.key_base}_energy_charges", {})
        self._attr_available = bool(self.seasons and self.charges)
