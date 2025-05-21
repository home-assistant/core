"""Calendar platform for Teslemetry integration."""

from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any

from attr import dataclass
from tesla_fleet_api.const import Scope

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TeslemetryConfigEntry
from .entity import TeslemetryEnergyInfoEntity, TeslemetryVehiclePollingEntity
from .models import TeslemetryVehicleData


# Helper function to generate rrule day strings
def get_rrule_days(days_of_week: int) -> list[str]:
    """Get the rrule days for a days_of_week binary."""
    rrule_days_map = {
        0b0000001: "MO",
        0b0000010: "TU",
        0b0000100: "WE",
        0b0001000: "TH",
        0b0010000: "FR",
        0b0100000: "SA",
        0b1000000: "SU",
    }
    rrule_days = []
    for day_flag, day_code in rrule_days_map.items():
        if days_of_week & day_flag:
            rrule_days.append(day_code)
    return rrule_days


# Helper function to check if a date matches the days_of_week mask
def test_days_of_week(date: datetime, days_of_week: int) -> bool:
    """Check if a specific day is in the days_of_week binary."""
    return (days_of_week & (1 << date.weekday())) > 0


@dataclass
class Schedule:
    """A schedule for a vehicle or tariff."""

    name: str
    start_mins: timedelta
    end_mins: timedelta
    days_of_week: int
    uid: str
    location: str
    rrule: str | None = None

    def generate_upcoming_events(
        self, start_dt: datetime, end_dt: datetime
    ) -> Generator[CalendarEvent]:
        """Generate CalendarEvent objects for this schedule occurring strictly within the time range [start_dt, end_dt).

        Args:
            start_dt: The inclusive start datetime of the query range.
            end_dt: The exclusive end datetime of the query range.

        Yields:
            CalendarEvent: Event objects for occurrences within the range.

        """
        # Start iterating from the beginning of the day of start_dt
        current_day = dt_util.start_of_local_day(start_dt)

        while current_day < end_dt:
            # Check if the schedule runs on this day of the week
            if test_days_of_week(current_day, self.days_of_week):
                # Calculate the event's start and end datetime for the current day
                event_start = current_day + self.start_mins
                event_end = current_day + self.end_mins

                # Check if the calculated event overlaps with the query range [start_dt, end_dt)
                if event_start < end_dt and event_end > start_dt:
                    yield CalendarEvent(
                        start=event_start,
                        end=event_end,
                        summary=self.name,
                        description=self.location,  # Or a more specific description if available
                        location=self.location,
                        uid=self.uid,
                        rrule=self.rrule,
                    )

            # Move to the next day
            current_day += timedelta(days=1)

            # Optimization: If rrule indicates COUNT=1, stop after the first valid day found
            # However, the current rrule string doesn't reliably encode one-time nature
            # separate from days_of_week. Relying on the date iteration boundary is safer.
            # The original code had a `count < 7` check which is removed here in favor
            # of strictly adhering to start_dt and end_dt.


# Shared utility function to get sorted events from multiple schedules
async def async_get_sorted_schedule_events(
    schedules: list[Schedule], start_dt: datetime, end_dt: datetime
) -> list[CalendarEvent]:
    """Fetch events from multiple schedules within a time range and return them sorted by start time.

    Args:
        schedules: A list of Schedule objects.
        start_dt: The inclusive start datetime of the query range.
        end_dt: The exclusive end datetime of the query range.

    Returns:
        A list of CalendarEvent objects, sorted chronologically.

    """
    # Gather all events from all schedules within the given time range
    # This uses a nested list comprehension for conciseness.
    all_events: list[CalendarEvent] = [
        event
        for schedule in schedules
        for event in schedule.generate_upcoming_events(start_dt, end_dt)
    ]

    # Sort the collected events by their start time
    return sorted(all_events, key=lambda event: event.start)


# --- Vehicle Charge Schedule ---
class TeslemetryChargeSchedule(TeslemetryVehiclePollingEntity, CalendarEntity):
    """Vehicle Charge Schedule Calendar."""

    _attr_entity_registry_enabled_default = False
    schedules: list[Schedule]
    summary_format: str  # Use a format string for summary

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the charge schedule calendar."""
        self.schedules = []
        # Store format string, actual name might be None initially
        self.summary_format = (
            f"Charge scheduled for {data.device.get('name', 'Vehicle')}"
        )
        super().__init__(data, "charge_schedule_data_charge_schedules")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        next_event: CalendarEvent | None = None

        # Define a reasonable future limit for finding the 'next' event (e.g., 14 days)
        # Avoids iterating indefinitely if schedules are far in the future.
        future_limit = now + timedelta(days=14)

        for schedule in self.schedules:
            # Use the generator to find the first event for this schedule after 'now'
            try:
                # Get the first event yielded by the generator within the future limit
                first_occurrence = next(
                    schedule.generate_upcoming_events(now, future_limit), None
                )
            except StopIteration:
                # Generator finished without yielding anything in the range
                first_occurrence = None

            if first_occurrence:
                # If this is the first event found, or if it's earlier than the current 'next_event'
                if next_event is None or first_occurrence.start < next_event.start:
                    next_event = first_occurrence

        return next_event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range using the shared helper."""
        # Delegate to the shared function
        return await async_get_sorted_schedule_events(
            self.schedules, start_date, end_date
        )

    def _async_update_attrs(self) -> None:
        """Update the Calendar events by parsing raw schedule data."""
        raw_schedules_data = self._value or []
        self.schedules = []
        for schedule_data in raw_schedules_data:
            if not schedule_data.get("enabled") or not schedule_data.get(
                "days_of_week"
            ):
                continue

            start_time_min = schedule_data.get("start_time", 0)
            end_time_min = schedule_data.get("end_time", 0)
            start_enabled = schedule_data.get(
                "start_enabled", True
            )  # Assume enabled if key missing? API dependent.
            end_enabled = schedule_data.get("end_enabled", True)

            # Determine start and end timedeltas based on enabled flags and times
            if not end_enabled:
                start_mins = timedelta(minutes=start_time_min)
                end_mins = start_mins  # Treat as instantaneous if end is disabled
            elif not start_enabled:
                end_mins = timedelta(minutes=end_time_min)
                start_mins = end_mins  # Treat as instantaneous if start is disabled
            elif start_time_min > end_time_min:
                # Crosses midnight
                start_mins = timedelta(minutes=start_time_min)
                end_mins = timedelta(days=1, minutes=end_time_min)
            else:
                # Same day
                start_mins = timedelta(minutes=start_time_min)
                end_mins = timedelta(minutes=end_time_min)

            days_of_week = schedule_data["days_of_week"]
            rrule_days = get_rrule_days(days_of_week)
            rrule = f"FREQ=WEEKLY;WKST=MO;BYDAY={','.join(rrule_days)}"

            # Handle one-time schedules - modify rrule or handle in generator?
            # The original code added COUNT=1. Let's keep that for rrule consistency.
            # Note: The generator logic currently doesn't explicitly use rrule for iteration control,
            # it relies on date boundaries. But rrule is useful for calendar clients.
            if schedule_data.get("one_time"):
                rrule += ";COUNT=1"
                # If one_time, ensure days_of_week represents *only* the specific day? API dependent.

            self.schedules.append(
                Schedule(
                    name=schedule_data.get("name")
                    or self.summary_format,  # Use format string
                    start_mins=start_mins,
                    end_mins=end_mins,
                    days_of_week=days_of_week,
                    uid=str(
                        schedule_data.get("id", f"charge_{len(self.schedules)}")
                    ),  # Ensure unique ID
                    location=f"{schedule_data.get('latitude', '')},{schedule_data.get('longitude', '')}",
                    rrule=rrule,
                )
            )
        # Update the entity's availability based on whether schedules exist
        self._attr_available = bool(self.schedules)


class TeslemetryPreconditionSchedule(TeslemetryVehiclePollingEntity, CalendarEntity):
    """Vehicle Precondition Schedule Calendar."""

    _attr_entity_registry_enabled_default = False
    schedules: list[Schedule]
    summary_format: str

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the precondition schedule calendar."""
        self.schedules = []
        self.summary_format = (
            f"Precondition scheduled for {data.device.get('name', 'Vehicle')}"
        )
        super().__init__(data, "preconditioning_schedule_data_precondition_schedules")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        next_event: CalendarEvent | None = None
        future_limit = now + timedelta(days=14)  # Look ahead 14 days

        for schedule in self.schedules:
            try:
                first_occurrence = next(
                    schedule.generate_upcoming_events(now, future_limit), None
                )
            except StopIteration:
                first_occurrence = None

            if first_occurrence:
                if next_event is None or first_occurrence.start < next_event.start:
                    next_event = first_occurrence

        return next_event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range using the shared helper."""
        # Delegate to the shared function
        return await async_get_sorted_schedule_events(
            self.schedules, start_date, end_date
        )

    def _async_update_attrs(self) -> None:
        """Update the Calendar events by parsing raw schedule data."""
        raw_schedules_data = self._value or []
        self.schedules = []
        for schedule_data in raw_schedules_data:
            if not schedule_data.get("enabled") or not schedule_data.get(
                "days_of_week"
            ):
                continue

            # Preconditioning seems to be instantaneous based on original code
            precondition_time_min = schedule_data.get("precondition_time", 0)
            start_mins = timedelta(minutes=precondition_time_min)
            end_mins = start_mins  # Instantaneous event

            days_of_week = schedule_data["days_of_week"]
            rrule = None
            # Only set rrule if it's a recurring schedule
            if not schedule_data.get("one_time"):
                rrule_days = get_rrule_days(days_of_week)
                rrule = f"FREQ=WEEKLY;WKST=MO;BYDAY={','.join(rrule_days)}"

            self.schedules.append(
                Schedule(
                    name=schedule_data.get("name") or self.summary_format,
                    start_mins=start_mins,
                    end_mins=end_mins,
                    days_of_week=days_of_week,
                    uid=str(
                        schedule_data.get("id", f"precondition_{len(self.schedules)}")
                    ),
                    location=f"{schedule_data.get('latitude', '')},{schedule_data.get('longitude', '')}",
                    rrule=rrule,
                )
            )
        self._attr_available = bool(self.schedules)


# --- Energy Tariff Schedule (Largely Unchanged by this Refactoring) ---
@dataclass
class TariffPeriod:  # Renamed from TarrifPeriod
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

    # Vehicle Charge Schedules
    entities_to_add.extend(
        TeslemetryChargeSchedule(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )

    # Vehicle Precondition Schedules
    entities_to_add.extend(
        TeslemetryPreconditionSchedule(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )

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
