"""Entity representing a Jewish Calendar sensor."""

from dataclasses import dataclass

from hdate import Location
from hdate.translator import Language

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN

type JewishCalendarConfigEntry = ConfigEntry[JewishCalendarData]


@dataclass
class JewishCalendarData:
    """Jewish Calendar runtime dataclass."""

    language: Language
    diaspora: bool
    location: Location
    candle_lighting_offset: int
    havdalah_offset: int


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
        data = config_entry.runtime_data
        self._location = data.location
        self._language = data.language
        self._candle_lighting_offset = data.candle_lighting_offset
        self._havdalah_offset = data.havdalah_offset
        self._diaspora = data.diaspora
