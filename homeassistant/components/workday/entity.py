"""Base workday entity."""

from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime, timedelta

from holidays import HolidayBase, __version__ as python_holidays_version

from homeassistant.core import CALLBACK_TYPE, ServiceResponse, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import ALLOWED_DAYS, DOMAIN


class BaseWorkdayEntity(Entity):
    """Implementation of a base Workday entity."""

    _attr_has_entity_name = True
    _attr_translation_key = DOMAIN
    _attr_should_poll = False
    unsub: CALLBACK_TYPE | None = None

    def __init__(
        self,
        obj_holidays: HolidayBase,
        workdays: list[str],
        excludes: list[str],
        days_offset: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Workday entity."""
        self._obj_holidays = obj_holidays
        self._workdays = workdays
        self._excludes = excludes
        self._days_offset = days_offset
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="python-holidays",
            model=python_holidays_version,
            name=name,
        )

    def is_include(self, day: str, now: date) -> bool:
        """Check if given day is in the includes list."""
        if day in self._workdays:
            return True
        if "holiday" in self._workdays and now in self._obj_holidays:
            return True

        return False

    def is_exclude(self, day: str, now: date) -> bool:
        """Check if given day is in the excludes list."""
        if day in self._excludes:
            return True
        if "holiday" in self._excludes and now in self._obj_holidays:
            return True

        return False

    def get_next_interval(self, now: datetime) -> datetime:
        """Compute next time an update should occur."""
        tomorrow = dt_util.as_local(now) + timedelta(days=1)
        return dt_util.start_of_local_day(tomorrow)

    def _update_state_and_setup_listener(self) -> None:
        """Update state and setup listener for next interval."""
        now = dt_util.now()
        self.update_data(now)
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval(now)
        )

    @callback
    def point_in_time_listener(self, time_date: datetime) -> None:
        """Get the latest data and update state."""
        self._update_state_and_setup_listener()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Set up first update."""
        self._update_state_and_setup_listener()

    @abstractmethod
    def update_data(self, now: datetime) -> None:
        """Update data."""

    def check_date(self, check_date: date) -> ServiceResponse:
        """Service to check if date is workday or not."""
        return {"workday": self.date_is_workday(check_date)}

    def date_is_workday(self, check_date: date) -> bool:
        """Check if date is workday."""
        # Default is no workday
        is_workday = False

        # Get ISO day of the week (1 = Monday, 7 = Sunday)
        adjusted_date = check_date + timedelta(days=self._days_offset)
        day = adjusted_date.isoweekday() - 1
        day_of_week = ALLOWED_DAYS[day]

        if self.is_include(day_of_week, adjusted_date):
            is_workday = True

        if self.is_exclude(day_of_week, adjusted_date):
            is_workday = False

        return is_workday
