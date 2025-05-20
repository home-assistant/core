"""Data update coordinator for Jewish calendar."""

from dataclasses import dataclass
import datetime as dt
import logging

from hdate import HDateInfo, Location, Zmanim
from hdate.translator import Language

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type JewishCalendarConfigEntry = ConfigEntry[JewishCalendarUpdateCoordinator]


@dataclass
class JewishCalendarData:
    """Jewish Calendar runtime dataclass."""

    language: Language
    diaspora: bool
    location: Location
    candle_lighting_offset: int
    havdalah_offset: int
    dateinfo: HDateInfo | None = None
    zmanim: Zmanim | None = None


class JewishCalendarUpdateCoordinator(DataUpdateCoordinator[JewishCalendarData]):
    """Data update coordinator class for Jewish calendar."""

    config_entry: JewishCalendarConfigEntry
    _attr_should_poll = False
    event_unsub: CALLBACK_TYPE | None = None

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
        self._unsub_update: CALLBACK_TYPE | None = None

    async def async_update_data(self) -> JewishCalendarData:
        """Return HDate and Zmanim for today."""
        now = dt_util.now()
        _LOGGER.debug("Now: %s Location: %r", now, self.config_data.location)

        today = now.date()

        self.config_data.dateinfo = HDateInfo(today, self.config_data.diaspora)
        self.config_data.zmanim = Zmanim(
            date=today,
            location=self.config_data.location,
            candle_lighting_offset=self.config_data.candle_lighting_offset,
            havdalah_offset=self.config_data.havdalah_offset,
        )
        self.async_schedule_future_update()
        return self.config_data

    @callback
    def async_schedule_future_update(self) -> None:
        """Schedule the next update of the sensor for the upcoming midnight."""
        # Cancel any existing update
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

        # Calculate the next midnight
        next_midnight = dt_util.start_of_local_day() + dt.timedelta(days=1)

        _LOGGER.debug("Scheduling next update at %s", next_midnight)

        # Schedule update at next midnight
        self._unsub_update = event.async_track_point_in_time(
            self.hass, self._handle_midnight_update, next_midnight
        )

    @callback
    def _handle_midnight_update(self, _now: dt.datetime) -> None:
        """Handle midnight update callback."""
        self._unsub_update = None
        self.async_set_updated_data(self.config_data)

    async def async_shutdown(self) -> None:
        """Cancel any scheduled updates when the coordinator is shutting down."""
        await super().async_shutdown()
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

    def make_zmanim(self, date: dt.date) -> Zmanim:
        """Create a Zmanim object."""
        return Zmanim(
            date=date,
            location=self.config_data.location,
            candle_lighting_offset=self.config_data.candle_lighting_offset,
            havdalah_offset=self.config_data.havdalah_offset,
        )
