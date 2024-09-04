"""Generic entity for the WMS WebControl pro API integration."""

from __future__ import annotations

from wmspro.destination import Destination

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER


class WebControlProGenericEntity(Entity):
    """Foundation of all WMS based entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry_id: str, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        self._dest = dest
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model=dest.animationType.name,
            name=dest.name,
            serial_number=dest.id,
            suggested_area=dest.room.name,
            via_device=(DOMAIN, config_entry_id),
            configuration_url=f"http://{dest.host}/control",
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._dest.refresh()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return str(self._dest.id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._dest.available
