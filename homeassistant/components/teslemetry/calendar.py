"""Calendar platform for Teslemetry integration."""

from datetime import datetime, timedelta
from itertools import chain
from typing import Any

from attr import dataclass
from tesla_fleet_api.const import Scope

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TeslemetryConfigEntry
from .entity import TeslemetryEnergyInfoEntity, TeslemetryVehicleEntity
from .models import TeslemetryVehicleData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Calendar platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryChargeSchedule(vehicle, entry.runtime_data.scopes)
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryPreconditionSchedule(vehicle, entry.runtime_data.scopes)
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryTariffSchedule(energy, "tariff_content_v2")
                for energy in entry.runtime_data.energysites
                if energy.info_coordinator.data.get("tariff_content_v2_seasons")
            ),
            (
                TeslemetryTariffSchedule(energy, "tariff_content_v2_sell_tariff")
                for energy in entry.runtime_data.energysites
                if energy.info_coordinator.data.get(
                    "tariff_content_v2_sell_tariff_seasons"
                )
            ),
        )
    )


def get_rrule_days(days_of_week: int) -> list[str]:
    """Get the rrule days for a days_of_week binary."""

    rrule_days = []
    if days_of_week & 0b0000001:
        rrule_days.append("MO")
    if days_of_week & 0b0000010:
        rrule_days.append("TU")
    if days_of_week & 0b0000100:
        rrule_days.append("WE")
    if days_of_week & 0b0001000:
        rrule_days.append("TH")
    if days_of_week & 0b0010000:
        rrule_days.append("FR")
    if days_of_week & 0b0100000:
        rrule_days.append("SA")
    if days_of_week & 0b1000000:
        rrule_days.append("SU")
    return rrule_days


def test_days_of_week(date: datetime, days_of_week: int) -> bool:
    """Check if a specific day is in the days_of_week binary."""
    return days_of_week & 1 << date.weekday() > 0


@dataclass
class Schedule:
    """A schedule for a vehicle."""

    name: str
    start_mins: timedelta
    end_mins: timedelta
    days_of_week: int
    uid: str
    location: str
    rrule: str | None


class TeslemetryChargeSchedule(TeslemetryVehicleEntity, CalendarEntity):
    """Vehicle Charge Schedule Calendar."""

    _attr_entity_registry_enabled_default = False
    schedules: list[Schedule]
    summary: str

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""
        self.schedules = []
        self.summary = f"Charge scheduled for {data.device.get('name')}"
        super().__init__(data, "charge_schedule_data_charge_schedules")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        event = None
        for schedule in self.schedules:
            day = dt_util.start_of_local_day()
            while not event or day < event.start:
                if test_days_of_week(day, schedule.days_of_week):
                    start = day + schedule.start_mins
                    end = day + schedule.end_mins

                    if end > now and (not event or start < event.start):
                        event = CalendarEvent(
                            start=start,
                            end=end,
                            summary=schedule.name,
                            description=schedule.location,
                            location=schedule.location,
                            uid=schedule.uid,
                            rrule=schedule.rrule,
                        )
                day += timedelta(days=1)
        return event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        events = []
        for schedule in self.schedules:
            day = dt_util.start_of_local_day()
            count = 0

            # Iterate through the next 7 days for non-reoccuring schedules
            # or every day for recurring schedules, until end_date
            while day < end_date and (count < 7 or schedule.rrule):
                if day >= start_date and test_days_of_week(day, schedule.days_of_week):
                    start = day + schedule.start_mins
                    end = day + schedule.end_mins
                    if (end > start_date) and (start < end_date):
                        events.append(
                            CalendarEvent(
                                start=start,
                                end=end,
                                summary=schedule.name,
                                description=schedule.location,
                                location=schedule.location,
                                uid=schedule.uid,
                                rrule=schedule.rrule,
                            )
                        )
                day += timedelta(days=1)
                count += 1

        events.sort(key=lambda x: x.start)
        return events

    def _async_update_attrs(self) -> None:
        """Update the Calendar events."""
        schedules = self._value or []
        self.schedules = []
        for schedule in schedules:
            if not schedule["enabled"] or not schedule["days_of_week"]:
                continue
            if not schedule["end_enabled"]:
                start_mins = timedelta(minutes=schedule["start_time"])
                end_mins = start_mins
            elif not schedule["start_enabled"]:
                end_mins = timedelta(minutes=schedule["end_time"])
                start_mins = end_mins
            elif schedule["start_time"] > schedule["end_time"]:
                start_mins = timedelta(minutes=schedule["start_time"])
                end_mins = timedelta(days=1, minutes=schedule["end_time"])
            else:
                start_mins = timedelta(minutes=schedule["start_time"])
                end_mins = timedelta(minutes=schedule["end_time"])

            rrule = f"FREQ=WEEKLY;WKST=MO;BYDAY={','.join(get_rrule_days(schedule['days_of_week']))}"
            if schedule["one_time"]:
                rrule += ";COUNT=1"

            self.schedules.append(
                Schedule(
                    name=schedule["name"] or self.summary,
                    start_mins=start_mins,
                    end_mins=end_mins,
                    days_of_week=schedule["days_of_week"],
                    uid=str(schedule["id"]),
                    location=f"{schedule['latitude']},{schedule['longitude']}",
                    rrule=rrule,
                )
            )


class TeslemetryPreconditionSchedule(TeslemetryVehicleEntity, CalendarEntity):
    """Vehicle Precondition Schedule Calendar."""

    _attr_entity_registry_enabled_default = False
    events: list[CalendarEvent]
    summary: str

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""
        self.summary = f"Precondition scheduled for {data.device.get('name')}"
        super().__init__(data, "preconditioning_schedule_data_precondition_schedules")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        event = None

        for schedule in self.schedules:
            day = dt_util.start_of_local_day()

            # Find the next occurrence of the schedule in time
            # but dont look past an existing valid event
            while not event or day < event.start:
                # Confirm the schedule runs on this day of the week
                if test_days_of_week(day, schedule.days_of_week):
                    start = day + schedule.start_mins
                    end = day + schedule.end_mins

                    # Confirm schedule in in the future, and before any other valid event
                    if end > now and (not event or start < event.start):
                        event = CalendarEvent(
                            start=start,
                            end=end,
                            summary=schedule.name,
                            description=schedule.location,
                            location=schedule.location,
                            uid=schedule.uid,
                            rrule=schedule.rrule,
                        )
                day += timedelta(days=1)
        return event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        events = []
        # Iterate through each schedule
        for schedule in self.schedules:
            day = dt_util.start_of_local_day()
            count = 0

            # Iterate through the next 7 days for non-reoccuring schedules,
            # or every day for recurring schedules, until end_date
            while day < end_date and (count < 7 or schedule.rrule):
                # Ensure that the event is within the specified date range, and on this day of the week.
                if day >= start_date and test_days_of_week(day, schedule.days_of_week):
                    start = day + schedule.start_mins
                    end = day + schedule.end_mins
                    # Check if the event is within the requested date range
                    if (end > start_date) and (start < end_date):
                        events.append(
                            CalendarEvent(
                                start=start,
                                end=end,
                                summary=schedule.name,
                                description=schedule.location,
                                location=schedule.location,
                                uid=schedule.uid,
                                rrule=schedule.rrule,
                            )
                        )
                day += timedelta(days=1)
                count += 1

        # Sort events by start time
        events.sort(key=lambda x: x.start)
        return events

    def _async_update_attrs(self) -> None:
        """Update the Calendar events."""
        schedules = self._value or []
        self.schedules = []
        for schedule in schedules:
            if not schedule["enabled"] or not schedule["days_of_week"]:
                continue
            start_mins = timedelta(minutes=schedule["precondition_time"])
            end_mins = timedelta(minutes=schedule["precondition_time"])

            rrule = None
            if not schedule["one_time"]:
                rrule = f"FREQ=WEEKLY;WKST=MO;BYDAY={','.join(get_rrule_days(schedule['days_of_week']))}"

            self.schedules.append(
                Schedule(
                    name=schedule["name"] or self.summary,
                    start_mins=start_mins,
                    end_mins=end_mins,
                    days_of_week=schedule["days_of_week"],
                    uid=str(schedule["id"]),
                    location=f"{schedule['latitude']},{schedule['longitude']}",
                    rrule=rrule,
                )
            )


@dataclass
class TarrifPeriod:
    """A single tariff period."""

    name: str
    price: float
    from_hour: int = 0
    from_minute: int = 0
    to_hour: int = 0
    to_minute: int = 0


class TeslemetryTariffSchedule(TeslemetryEnergyInfoEntity, CalendarEntity):
    """Vehicle Charge Schedule Calendar."""

    seasons: dict[str, dict[str, Any]]
    charges: dict[str, dict[str, Any]]
    currency: str

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""

        now = dt_util.now()
        season = None
        for season_name, season_data in self.seasons.items():
            if not season_data:
                continue

            start = datetime(
                now.year,
                season_data["fromMonth"],
                season_data["fromDay"],
                tzinfo=now.tzinfo,
            )
            end = datetime(
                now.year,
                season_data["toMonth"],
                season_data["toDay"],
                tzinfo=now.tzinfo,
            ) + timedelta(days=1)

            if end <= now <= start:
                season = season_name
                break

        if not season:
            return None

        for name in self.seasons[season]["tou_periods"]:
            for period in self.seasons[season]["tou_periods"][name]["periods"]:
                day = now.weekday()
                if day < period.get("fromDayOfWeek", 0) or day > period.get(
                    "toDayOfWeek", 6
                ):
                    continue
                start_time = datetime(
                    now.year,
                    now.month,
                    now.day,
                    period.get("from_hour", 0) % 24,
                    period.get("from_minute", 0) % 60,
                    tzinfo=now.tzinfo,
                )
                end_time = datetime(
                    now.year,
                    now.month,
                    now.day,
                    period.get("to_hour", 0) % 24,
                    period.get("to_minute", 0) % 60,
                    tzinfo=now.tzinfo,
                )
                if end_time < start_time:
                    end_time += timedelta(days=1)
                if start_time < now < end_time:
                    price = self.charges.get(season, self.charges["ALL"])["rates"].get(
                        name, self.charges["ALL"]["rates"]["ALL"]
                    )
                    return CalendarEvent(
                        start=start_time,
                        end=end_time,
                        summary=f"{price}/kWh",
                        description=f"Seasons: {season}\nPeriod: {name}\nPrice: {price}/kWh",
                    )
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events: list[CalendarEvent] = []

        TZ = dt_util.get_default_time_zone()

        for year in range(start_date.year, end_date.year + 1):
            for season, season_data in self.seasons.items():
                if not season_data:
                    continue
                start = datetime(
                    year,
                    season_data["fromMonth"],
                    season_data["fromDay"],
                    tzinfo=TZ,
                )
                end = datetime(
                    year,
                    season_data["toMonth"],
                    season_data["toDay"],
                    tzinfo=TZ,
                ) + timedelta(days=1)

                # Skip if the range doesn't overlap with the season
                if end <= start_date or start >= end_date:
                    continue

                week: list[list[TarrifPeriod]] = [[], [], [], [], [], [], []]
                for name, period_data in self.seasons[season]["tou_periods"].items():
                    for period in period_data["periods"]:
                        # Iterate through the specified day of week range
                        for x in range(
                            period.get("fromDayOfWeek", 0),
                            period.get("toDayOfWeek", 6) + 1,
                        ):
                            week[x].append(
                                # Values can be
                                TarrifPeriod(
                                    name,
                                    self.charges.get(season, self.charges["ALL"])[
                                        "rates"
                                    ].get(name, self.charges["ALL"]["rates"]["ALL"]),
                                    period.get("fromHour", 0) % 24,
                                    period.get("fromMinute", 0) % 60,
                                    period.get("toHour", 0) % 24,
                                    period.get("toMinute", 0) % 60,
                                )
                            )

                # Find the overlap between the season and the requested time period
                start = max(start_date, start)
                end = min(end_date, end)

                # Iterate each day of that overlap
                date = start
                while date < end:
                    weekday = date.weekday()
                    for period in week[weekday]:
                        start_time = datetime(
                            date.year,
                            date.month,
                            date.day,
                            period.from_hour,
                            period.from_minute,
                            tzinfo=TZ,
                        )
                        end_time = datetime(
                            date.year,
                            date.month,
                            date.day,
                            period.to_hour,
                            period.to_minute,
                            tzinfo=TZ,
                        )
                        if end_time < start_time:
                            # Handle periods that span midnight
                            end_time += timedelta(days=1)
                        if end_time > start_date or start_time < end_date:
                            events.append(
                                CalendarEvent(
                                    start=start_time,
                                    end=end_time,
                                    summary=f"{period.price}/kWh",
                                    description=f"Seasons: {season}\nPeriod: {period.name}\nPrice: {period.price}/kWh",
                                )
                            )
                    date += timedelta(days=1)

        # Sort events by start time
        events.sort(key=lambda x: x.start)

        return events

    def _async_update_attrs(self) -> None:
        """Update the Calendar events."""
        if seasons := self.get(f"{self.key}_seasons"):
            self.seasons = seasons
        if charges := self.get(f"{self.key}_energy_charges"):
            self.charges = charges
