"""Entity representing a Jewish Calendar sensor."""

from typing import Any

from homeassistant.const import CONF_LANGUAGE, CONF_LOCATION
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_NAME,
    DOMAIN,
)


class JewishCalendarEntity(Entity):
    """An HA implementation for Jewish Calendar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        data: dict[str, Any],
        description: EntityDescription,
    ) -> None:
        """Initialize a Jewish Calendar entity."""
        self.entity_description = description
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=DEFAULT_NAME,
        )
        self._location = data[CONF_LOCATION]
        self._hebrew = data[CONF_LANGUAGE] == "hebrew"
        self._candle_lighting_offset = data[CONF_CANDLE_LIGHT_MINUTES]
        self._havdalah_offset = data[CONF_HAVDALAH_OFFSET_MINUTES]
        self._diaspora = data[CONF_DIASPORA]
