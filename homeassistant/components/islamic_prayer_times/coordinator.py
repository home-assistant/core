"""Coordinator for the Islamic prayer times integration."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, cast, override

from prayer_times_calculator_offline import (
    CalculationMethodError,
    PrayerTimesCalculator,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CALC_METHOD,
    CONF_ISHA_CALENDAR_END,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    DEFAULT_CALC_METHOD,
    DEFAULT_ISHA_CALENDAR_END,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
    ISHA_CALENDAR_ENDS,
)

_LOGGER = logging.getLogger(__name__)

PRAYER_WINDOW_ENDS = {
    "Fajr": "Sunrise",
    "Dhuhr": "Asr",
    "Asr": "Sunset",
    "Maghrib": "Isha",
    "Isha": "Midnight",
}


@dataclass(frozen=True)
class PrayerWindow:
    """A calculated prayer's display window."""

    name: str
    start: datetime
    end: datetime
    description: str | None = None


def _prayer_time(times: dict[str, Any], name: str) -> datetime:
    """Read an aware prayer timestamp in UTC."""
    try:
        value = dt_util.parse_datetime(times[name], raise_on_error=True)
    except (KeyError, TypeError, ValueError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="calculation_failed"
        ) from err
    if value is None or value.tzinfo is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="calculation_failed"
        )
    return dt_util.as_utc(value)


type IslamicPrayerTimesConfigEntry = ConfigEntry[IslamicPrayerDataUpdateCoordinator]


class IslamicPrayerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, datetime]]):
    """Islamic Prayer Client Object."""

    config_entry: IslamicPrayerTimesConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: IslamicPrayerTimesConfigEntry
    ) -> None:
        """Initialize the Islamic Prayer client."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.latitude = config_entry.data[CONF_LATITUDE]
        self.longitude = config_entry.data[CONF_LONGITUDE]
        self.event_unsub: CALLBACK_TYPE | None = None
        self.prayer_times: dict[date, dict[str, Any]] = {}
        self.prayer_windows: list[PrayerWindow] | None = None
        self._prayer_boundary_unsub: CALLBACK_TYPE | None = None

    @property
    def current_prayer(self) -> PrayerWindow | None:
        """Return the first active window, matching the calendar during overlaps."""
        now = dt_util.utcnow()
        return next(
            (
                window
                for window in self.prayer_windows or ()
                if window.start <= now < window.end
            ),
            None,
        )

    @property
    def next_prayer(self) -> PrayerWindow | None:
        """Return the next prayer whose start is strictly in the future."""
        now = dt_util.utcnow()
        return next(
            (window for window in self.prayer_windows or () if window.start > now),
            None,
        )

    def get_prayer_windows(
        self, day: date, times: dict[str, Any] | None = None
    ) -> list[PrayerWindow]:
        """Build the shared calendar and sensor windows for a calculation date."""
        if times is None:
            times = self._get_window_times(day)
        windows: list[PrayerWindow] = []
        for name, end_name in PRAYER_WINDOW_ENDS.items():
            start = _prayer_time(times, name)
            if name == "Isha":
                end_name = ISHA_CALENDAR_ENDS[
                    self.config_entry.options.get(
                        CONF_ISHA_CALENDAR_END, DEFAULT_ISHA_CALENDAR_END
                    )
                ]
            end = _prayer_time(times, end_name)
            description = None
            # Adjusted twilight can fall at or after the selected night boundary.
            if name == "Isha" and (end_name == "Fajr" or end <= start):
                next_times = self._get_window_times(day + timedelta(days=1))
                end = _prayer_time(next_times, "Fajr")
                if end <= start:
                    end = start + timedelta(minutes=10)
                    description = "Isha start marker (10-minute display duration)."
            if end <= start or (windows and start < windows[-1].end):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="calculation_failed"
                )
            windows.append(PrayerWindow(name, start, end, description))
        return windows

    def _get_window_times(self, day: date) -> dict[str, Any]:
        """Calculate window data, translating known calculation failures."""
        try:
            return self.get_new_prayer_times(day)
        except (ValueError, ArithmeticError, CalculationMethodError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="calculation_failed"
            ) from err

    @callback
    def _schedule_prayer_boundary(self) -> None:
        """Update context sensors at boundaries without rolling over sensor times."""
        if self._prayer_boundary_unsub:
            self._prayer_boundary_unsub()
            self._prayer_boundary_unsub = None
        now = dt_util.utcnow()
        boundary = min(
            (
                time
                for window in self.prayer_windows or ()
                for time in (window.start, window.end)
                if time > now
            ),
            default=None,
        )
        if boundary is not None:
            self._prayer_boundary_unsub = async_track_point_in_time(
                self.hass, self._handle_prayer_boundary, boundary
            )

    @callback
    def _handle_prayer_boundary(self, _: datetime) -> None:
        """Publish current and next prayer changes, then track the next boundary."""
        self._prayer_boundary_unsub = None
        self._schedule_prayer_boundary()
        self.async_update_listeners()

    @override
    async def async_shutdown(self) -> None:
        """Cancel the prayer boundary timer when the entry is unloaded."""
        if self._prayer_boundary_unsub:
            self._prayer_boundary_unsub()
            self._prayer_boundary_unsub = None
        await super().async_shutdown()

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)  # type: ignore[no-any-return]

    @property
    def lat_adj_method(self) -> str:
        """Return the latitude adjustment method."""
        return str(
            self.config_entry.options.get(
                CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD
            ).replace("_", " ")
        )

    @property
    def midnight_mode(self) -> str:
        """Return the midnight mode."""
        return self.config_entry.options.get(CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE)  # type: ignore[no-any-return]

    @property
    def school(self) -> str:
        """Return the school."""
        return self.config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL)  # type: ignore[no-any-return]

    def get_new_prayer_times(self, for_date: date) -> dict[str, Any]:
        """Fetch prayer times for the specified date."""
        calc = PrayerTimesCalculator(
            latitude=self.latitude,
            longitude=self.longitude,
            calculation_method=self.calc_method,
            latitudeAdjustmentMethod=self.lat_adj_method,
            midnightMode=self.midnight_mode,
            school=self.school,
            date=str(for_date),
            iso8601=True,
        )
        return cast(dict[str, Any], calc.fetch_prayer_times())

    @callback
    def async_schedule_future_update(self, midnight_dt: datetime) -> None:
        """Schedule future update for sensors.

        The least surprising behaviour is to load the next day's prayer times only
        after the current day's prayers are complete. We will take the fiqhi opinion
        that Isha should be prayed before Islamic midnight
        (which may be before or after 12:00 midnight), and thus
        we will switch to the next day's timings at Islamic
        midnight.

        The +1s is to ensure that any automations predicated
        on the arrival of Islamic midnight will run.

        """
        _LOGGER.debug("Scheduling next update for Islamic prayer times")

        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_request_update, midnight_dt + timedelta(seconds=1)
        )

    async def async_request_update(self, _: datetime) -> None:
        """Request update from coordinator."""
        await self.async_request_refresh()

    @override
    async def _async_update_data(self) -> dict[str, datetime]:
        """Update sensors with new prayer times.

        Prayer time calculations "roll over" at 12:00 midnight
        but this does not mean that all prayers occur within
        that Gregorian calendar day. For instance Jasper, Alta.
        sees Isha occur after 00:00 in the summer. It is
        similarly possible (albeit less likely) that Fajr
        occurs before 00:00.

        As such, to ensure that no prayer times are
        "unreachable" (e.g. we always see the Isha timestamp
        pass before loading the next day's times), we calculate
        3 days' worth of times (-1, 0, +1 days) and select the
        appropriate set based on Islamic midnight.

        The calculation is inexpensive, so there is no need to cache it.
        """

        # Zero out the us component to maintain consistent rollover at T+1s
        now = dt_util.now().replace(microsecond=0)
        yesterday_times = self.get_new_prayer_times((now - timedelta(days=1)).date())
        today_times = self.get_new_prayer_times(now.date())
        tomorrow_times = self.get_new_prayer_times((now + timedelta(days=1)).date())
        self.prayer_times = {
            (now - timedelta(days=1)).date(): yesterday_times,
            now.date(): today_times,
            (now + timedelta(days=1)).date(): tomorrow_times,
        }

        if (
            yesterday_midnight := dt_util.parse_datetime(yesterday_times["Midnight"])
        ) and now <= yesterday_midnight:
            prayer_times = yesterday_times
        elif (
            tomorrow_midnight := dt_util.parse_datetime(today_times["Midnight"])
        ) and now > tomorrow_midnight:
            prayer_times = tomorrow_times
        else:
            prayer_times = today_times

        # introduced in prayer-times-calculator 0.0.8
        prayer_times.pop("date", None)

        prayer_times_info: dict[str, datetime] = {}
        for prayer, time in prayer_times.items():
            if prayer_time := dt_util.parse_datetime(time):
                prayer_times_info[prayer] = dt_util.as_utc(prayer_time)

        try:
            windows: list[PrayerWindow] = []
            day = dt_util.as_utc(now).date() - timedelta(days=1)
            # Include the next prayer throughout the cache's lifetime until rollover.
            last_day = dt_util.as_utc(
                prayer_times_info["Midnight"] + timedelta(seconds=1)
            ).date() + timedelta(days=1)
            while day <= last_day:
                windows.extend(self.get_prayer_windows(day, self.prayer_times.get(day)))
                day += timedelta(days=1)
            self.prayer_windows = sorted(windows, key=lambda window: window.start)
        except HomeAssistantError:
            self.prayer_windows = None
        self._schedule_prayer_boundary()
        self.async_schedule_future_update(prayer_times_info["Midnight"])
        return prayer_times_info
