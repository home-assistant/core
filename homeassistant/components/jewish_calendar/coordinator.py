"""Data update coordinator for Jewish calendar."""

from dataclasses import dataclass
import datetime as dt
import logging

from hdate import HDateInfo, Location, Zmanim
from hdate.translator import Language

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type JewishCalendarConfigEntry = ConfigEntry[JewishCalendarUpdateCoordinator]


@dataclass
class JewishCalendarResults:
    """Jewish Calendar results dataclass."""

    daytime_date: HDateInfo
    after_shkia_date: HDateInfo
    after_tzais_date: HDateInfo
    zmanim: Zmanim


@dataclass
class JewishCalendarData:
    """Jewish Calendar runtime dataclass."""

    language: Language
    diaspora: bool
    location: Location
    candle_lighting_offset: int
    havdalah_offset: int
    results: JewishCalendarResults | None = None

    def make_zmanim(self, date: dt.date | None = None) -> Zmanim:
        """Create a Zmanim object."""
        if date is None:
            date = dt.date.today()
        return Zmanim(
            date=date,
            location=self.location,
            candle_lighting_offset=self.candle_lighting_offset,
            havdalah_offset=self.havdalah_offset,
            language=self.language,
        )


class JewishCalendarUpdateCoordinator(DataUpdateCoordinator[JewishCalendarData]):
    """Data update coordinator class for Jewish calendar."""

    config_entry: JewishCalendarConfigEntry
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: JewishCalendarConfigEntry,
        data: JewishCalendarData,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_method=self.async_update_data,
        )
        self.config_data = data
        self.event_unsub: CALLBACK_TYPE | None = None

    async def async_update_data(self) -> JewishCalendarData:
        """Return four data points.

        HDate for today, after_sunset and after_tzais.
        Zmanim for today. (Zmanim are considered based on the Gregorian date).
        """
        now = dt_util.now()
        _LOGGER.debug("Now: %s Location: %r", now, self.config_data.location)

        today = now.date()
        event_date = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)

        if event_date is None:
            _LOGGER.error("Can't get sunset event date for %s", today)
            raise ValueError

        sunset = dt_util.as_local(event_date)

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        daytime_date = HDateInfo(
            today,
            diaspora=self.config_data.diaspora,
            language=self.config_data.language,
        )

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area
        # (aka "Bein Hashmashot"  # codespell:ignore
        # - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = daytime_date
        today_times = self.config_data.make_zmanim(today)

        if now > sunset:
            after_shkia_date = daytime_date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = daytime_date.next_day

        self.config_data.results = JewishCalendarResults(
            daytime_date, after_shkia_date, after_tzais_date, today_times
        )
        # self.async_schedule_future_update()
        return self.config_data

    @callback
    def async_schedule_future_update(self) -> None:
        """Schedule the next update of the sensor."""
        assert self.config_data.results, "No results to schedule"
        zmanim = self.config_data.results.zmanim
        updates = [zmanim.netz_hachama.local + dt.timedelta(days=1), zmanim.shkia.local]
        if zmanim.candle_lighting:
            updates.append(zmanim.candle_lighting)
        if zmanim.havdalah:
            updates.append(zmanim.havdalah)

        now = dt_util.now()
        next_update = min([upd for upd in updates if upd], key=lambda x: x - now)
        # self.update_interval = next_update - now
        self._cancel_scheduled_update()  # Cancel any existing schedule
        self._unsub_update = async_track_point_in_time(
            self.hass, self._handle_scheduled_update, next_update
        )

        @callback
        async def _handle_scheduled_update(self, _):
            await self._async_update_data()
            self.async_schedule_future_update()
