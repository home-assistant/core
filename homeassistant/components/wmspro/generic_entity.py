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

    def __init__(self, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        super().__init__()
        self._dest = dest

    async def async_update(self) -> None:
        """Update the entity."""
        await self._dest.refresh()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self._dest.id}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._dest.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model=self._dest.animationType.name,
            name=self._dest.name,
            serial_number=self._dest.id,
            suggested_area=self._dest.room.name,
            via_device=(DOMAIN, self._dest.host),
            configuration_url=f"http://{self._dest.host}/control",
        )
