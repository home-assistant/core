"""Calendar platform for Teslemetry integration."""

from datetime import datetime, timedelta
from typing import Any

from attr import dataclass

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TeslemetryConfigEntry
from .entity import TeslemetryEnergyInfoEntity


@dataclass
class TariffPeriod:
    """A single tariff period."""

    name: str
    price: float
    from_hour: int = 0
    from_minute: int = 0
    to_hour: int = 0
    to_minute: int = 0


class TeslemetryTariffSchedule(TeslemetryEnergyInfoEntity, CalendarEntity):
    """Energy Site Tariff Schedule Calendar."""

    # Define attributes for clarity
    seasons: dict[str, dict[str, Any]] = {}
    charges: dict[str, dict[str, Any]] = {}
    currency: str = ""  # Should be fetched from config or site info if available
    key_base: str  # Store the base key ('tariff_content_v2' or 'tariff_content_v2_sell_tariff')

    def __init__(
        self,
        data: Any,  # Replace Any with specific EnergySite data type if available
        key_base: str,
    ) -> None:
        """Initialize the tariff schedule calendar."""
        self.key_base = key_base
        super().__init__(data, key_base)  # Use one key for initial check

    @property
    def event(self) -> CalendarEvent | None:
        """Return the *current* active tariff event."""
        # This method finds the currently active period, not the *next* upcoming one.
        # Keeping original logic as refactoring focused on the other schedule types.
        now = dt_util.now()
        current_season_name = self._get_current_season(now)

        if not current_season_name or not self.seasons.get(current_season_name):
            return None

        season_data = self.seasons[current_season_name]
        tou_periods = season_data.get("tou_periods", {})

        for period_name, period_group in tou_periods.items():
            for period_def in period_group.get("periods", []):
                # Check if today is within the period's day of week range
                day_of_week = now.weekday()  # Monday is 0, Sunday is 6
                from_day = period_def.get("fromDayOfWeek", 0)
                to_day = period_def.get("toDayOfWeek", 6)
                if not (from_day <= day_of_week <= to_day):
                    continue

                # Calculate start and end times for today
                from_hour = period_def.get("fromHour", 0) % 24
                from_minute = period_def.get("fromMinute", 0) % 60
                to_hour = period_def.get("toHour", 0) % 24
                to_minute = period_def.get("toMinute", 0) % 60

                start_time = now.replace(
                    hour=from_hour, minute=from_minute, second=0, microsecond=0
                )
                end_time = now.replace(
                    hour=to_hour, minute=to_minute, second=0, microsecond=0
                )

                # Handle midnight crossing for the end time
                if end_time <= start_time:
                    # If end time is on or before start time, it means it ends the next day
                    potential_end_time = end_time + timedelta(days=1)
                    # Check if 'now' is between start_time today and end_time tomorrow
                    if start_time <= now < potential_end_time:
                        end_time = potential_end_time  # Use the next day's end time
                    # Check if 'now' is between start_time yesterday (crossing midnight) and end_time today
                    elif (start_time - timedelta(days=1)) <= now < end_time:
                        start_time -= timedelta(days=1)  # Use yesterday's start time
                    else:
                        continue  # 'now' is not within this period
                elif not (start_time <= now < end_time):
                    continue  # 'now' is not within this period (same day)

                # Found the active period
                price = self._get_price_for_period(current_season_name, period_name)
                price_str = f"{price:.2f}/kWh" if price is not None else "Unknown Price"

                return CalendarEvent(
                    start=start_time,
                    end=end_time,
                    summary=f"{period_name.capitalize().replace('_', ' ')}: {price_str}",
                    description=(
                        f"Season: {current_season_name.capitalize()}\n"
                        f"Period: {period_name.capitalize().replace('_', ' ')}\n"
                        f"Price: {price_str}"
                    ),
                    uid=f"{self.key_base}_{current_season_name}_{period_name}_{start_time.isoformat()}",
                )

        return None  # No active period found for the current time and season

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events (tariff periods) within a datetime range."""
        # Keeping original logic structure, but with minor cleanups.
        events: list[CalendarEvent] = []

        # Ensure start_date and end_date are timezone-aware (using local)
        start_date = dt_util.as_local(start_date)
        end_date = dt_util.as_local(end_date)

        # Iterate through each day in the requested range
        current_day = dt_util.start_of_local_day(start_date)
        while current_day < end_date:
            season_name = self._get_current_season(current_day)
            if not season_name or not self.seasons.get(season_name):
                current_day += timedelta(days=1)
                continue

            season_data = self.seasons[season_name]
            tou_periods = season_data.get("tou_periods", {})
            day_of_week = current_day.weekday()

            for period_name, period_group in tou_periods.items():
                for period_def in period_group.get("periods", []):
                    # Check if the current day matches the period's day range
                    from_day = period_def.get("fromDayOfWeek", 0)
                    to_day = period_def.get("toDayOfWeek", 6)
                    if not (from_day <= day_of_week <= to_day):
                        continue

                    # Calculate start and end times for the current day
                    from_hour = period_def.get("fromHour", 0) % 24
                    from_minute = period_def.get("fromMinute", 0) % 60
                    to_hour = period_def.get("toHour", 0) % 24
                    to_minute = period_def.get("toMinute", 0) % 60

                    start_time = current_day.replace(
                        hour=from_hour, minute=from_minute, second=0, microsecond=0
                    )
                    end_time = current_day.replace(
                        hour=to_hour, minute=to_minute, second=0, microsecond=0
                    )

                    # Handle midnight crossing
                    if end_time <= start_time:
                        end_time += timedelta(days=1)

                    # Check if the event overlaps with the query range [start_date, end_date)
                    if start_time < end_date and end_time > start_date:
                        price = self._get_price_for_period(season_name, period_name)
                        price_str = (
                            f"{price:.2f}/kWh" if price is not None else "Unknown Price"
                        )
                        events.append(
                            CalendarEvent(
                                start=start_time,
                                end=end_time,
                                summary=f"{period_name.capitalize().replace('_', ' ')}: {price_str}",
                                description=(
                                    f"Season: {season_name.capitalize()}\n"
                                    f"Period: {period_name.capitalize().replace('_', ' ')}\n"
                                    f"Price: {price_str}"
                                ),
                                # Create a unique ID for each occurrence
                                uid=f"{self.key_base}_{season_name}_{period_name}_{start_time.isoformat()}",
                            )
                        )

            current_day += timedelta(days=1)

        # Sort events by start time (although daily iteration might already achieve this)
        events.sort(key=lambda x: x.start)
        return events

    def _get_current_season(self, date_to_check: datetime) -> str | None:
        """Determine the active season for a given date."""
        local_date = dt_util.as_local(date_to_check)
        year = local_date.year

        for season_name, season_data in self.seasons.items():
            if not season_data:
                continue

            # Create timezone-aware start and end dates for the season
            try:
                from_month = season_data["fromMonth"]
                from_day = season_data["fromDay"]
                to_month = season_data["toMonth"]
                to_day = season_data["toDay"]

                # Handle potential year wrapping for seasons crossing New Year
                start_year = year
                end_year = year

                # If start month is later than end month, the season crosses the year boundary
                if from_month > to_month or (
                    from_month == to_month and from_day > to_day
                ):
                    # If the date_to_check is in the start month or later, it's this year's season start
                    if local_date.month > from_month or (
                        local_date.month == from_month and local_date.day >= from_day
                    ):
                        end_year = year + 1  # Season ends next year
                    # Otherwise, the date must be before the end month/day, meaning it's part of the season that started last year
                    else:
                        start_year = year - 1  # Season started last year
                # Else: Season is within the same calendar year

                season_start = local_date.replace(
                    year=start_year,
                    month=from_month,
                    day=from_day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                # End date is exclusive, so add one day to the 'toDay'
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
            except (KeyError, ValueError):
                # Handle potential issues with season data format
                continue  # Skip this season if data is invalid

        return None  # No matching season found

    def _get_price_for_period(self, season_name: str, period_name: str) -> float | None:
        """Get the price for a specific season and period name."""
        try:
            # Find the rates for the season, fallback to "ALL" season if specific not found
            season_charges = self.charges.get(season_name, self.charges.get("ALL", {}))
            rates = season_charges.get("rates", {})
            # Find the price for the period, fallback to "ALL" period if specific not found
            price = rates.get(period_name, rates.get("ALL"))
            return float(price) if price is not None else None
        except (KeyError, ValueError, TypeError):
            return None  # Return None if price cannot be determined

    def _async_update_attrs(self) -> None:
        """Update the Calendar attributes from coordinator data."""
        # Fetch latest seasons and charges data using the base key
        self.seasons = self.coordinator.data.get(f"{self.key_base}_seasons", {})
        self.charges = self.coordinator.data.get(f"{self.key_base}_energy_charges", {})

        # Update availability based on whether necessary data is present
        self._attr_available = bool(self.seasons and self.charges)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Calendar platform from a config entry."""

    entities_to_add: list[CalendarEntity] = []

    # Energy Site Tariff Schedules (Buy)
    entities_to_add.extend(
        TeslemetryTariffSchedule(energy, "tariff_content_v2")
        for energy in entry.runtime_data.energysites
        if energy.info_coordinator.data.get("tariff_content_v2_seasons")
    )

    # Energy Site Tariff Schedules (Sell)
    entities_to_add.extend(
        TeslemetryTariffSchedule(energy, "tariff_content_v2_sell_tariff")
        for energy in entry.runtime_data.energysites
        if energy.info_coordinator.data.get("tariff_content_v2_sell_tariff_seasons")
    )

    async_add_entities(entities_to_add)
