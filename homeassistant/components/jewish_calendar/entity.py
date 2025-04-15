"""Entity representing a Jewish Calendar sensor."""

from hdate.hebrew_date import Months
from hdate.parasha import Parasha

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .coordinator import JewishCalendarConfigEntry


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
        self.coordinator = config_entry.runtime_data
        config = self.coordinator.data
        self.values = config.results
        self._location = config.location
        self._language = config.language
        self._candle_lighting_offset = config.candle_lighting_offset
        self._havdalah_offset = config.havdalah_offset
        self._diaspora = config.diaspora
        for month in Months:
            month.set_language(config.language)
        for p in Parasha:
            p.set_language(config.language)
