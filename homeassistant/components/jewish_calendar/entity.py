"""Entity representing a Jewish Calendar sensor."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DEFAULT_NAME, DOMAIN


class JewishCalendarEntity(Entity):
    """An HA implementation for Jewish Calendar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
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
