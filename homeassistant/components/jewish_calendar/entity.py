"""Entity representing a Jewish Calendar sensor."""

from dataclasses import dataclass
import datetime as dt

from hdate import HDateInfo, Location, Zmanim
from hdate.translator import Language, set_language

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN

type JewishCalendarConfigEntry = ConfigEntry[JewishCalendarData]


@dataclass
class JewishCalendarDataResults:
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
    results: JewishCalendarDataResults | None = None


class JewishCalendarEntity(Entity):
    """An HA implementation for Jewish Calendar entity."""

    _attr_has_entity_name = True

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
        return Zmanim(
            date=date,
            location=self.data.location,
            candle_lighting_offset=self.data.candle_lighting_offset,
            havdalah_offset=self.data.havdalah_offset,
        )
