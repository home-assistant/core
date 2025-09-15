"""Entity representing a Jewish Calendar sensor."""

from abc import abstractmethod
from dataclasses import dataclass
from functools import lru_cache
import datetime as dt
import logging

from hdate import HDateInfo, Location, Zmanim
from hdate.translator import Language, set_language

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type JewishCalendarConfigEntry = ConfigEntry[JewishCalendarData]


@dataclass
class JewishCalendarDataResults:
    """Jewish Calendar results dataclass."""

    dateinfo: HDateInfo
    zmanim: Zmanim


@lru_cache(maxsize=1)
def _make_zmanim(
    date: dt.date,
    location: Location,
    candle_lighting_offset: int,
    havdalah_offset: int,
) -> Zmanim:
    """Create a Zmanim object."""
    return Zmanim(date, location, candle_lighting_offset, havdalah_offset)


@lru_cache(maxsize=1)
def _create_results(
    date: dt.date,
    diaspora: bool,
    location: Location,
    candle_lighting_offset: int,
    havdalah_offset: int,
) -> None:
    """Create results object."""
    zmanim = _make_zmanim(date, location, candle_lighting_offset, havdalah_offset)
    dateinfo = HDateInfo(date, diaspora)
    return JewishCalendarDataResults(dateinfo, zmanim)


@dataclass
class JewishCalendarData:
    """Jewish Calendar runtime dataclass."""

    language: Language
    diaspora: bool
    location: Location
    candle_lighting_offset: int
    havdalah_offset: int
    results: JewishCalendarDataResults | None = None


class JewishCalendarEntity(Entity):
    """An HA implementation for Jewish Calendar entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _update_unsub: CALLBACK_TYPE | None = None

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a Jewish Calendar entity."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
        )
        self.data = config_entry.runtime_data
        set_language(self.data.language)

    def make_zmanim(self, date: dt.date) -> Zmanim:
        """Create a Zmanim object."""
        return _make_zmanim(
            date=date,
            location=self.data.location,
            candle_lighting_offset=self.data.candle_lighting_offset,
            havdalah_offset=self.data.havdalah_offset,
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._schedule_update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._update_unsub:
            self._update_unsub()
            self._update_unsub = None
        return await super().async_will_remove_from_hass()

    @abstractmethod
    def _update_times(self, zmanim: Zmanim) -> list[dt.datetime | None]:
        """Return a list of times to update the sensor."""

    def _schedule_update(self) -> None:
        """Schedule the next update of the sensor."""
        now = dt_util.now()
        zmanim = self.make_zmanim(now.date())
        update = dt_util.start_of_local_day() + dt.timedelta(days=1)

        for update_time in self._update_times(zmanim):
            if update_time is not None and now < update_time < update:
                update = update_time

        if self._update_unsub:
            self._update_unsub()
        self._update_unsub = event.async_track_point_in_time(
            self.hass, self._update, update
        )

    @callback
    def _update(self, now: dt.datetime | None = None) -> None:
        """Update the sensor data."""
        self._update_unsub = None
        self._schedule_update()
        self.create_results(now)
        self.async_write_ha_state()

    def create_results(self, now: dt.datetime | None = None) -> None:
        """Create the results for the sensor."""
        if now is None:
            now = dt_util.now()

        _LOGGER.debug("Now: %s Location: %r", now, self.data.location)

        self.data.results = _create_results(
            now.date(),
            self.data.diaspora,
            self.data.location,
            self.data.candle_lighting_offset,
            self.data.havdalah_offset,
        )
