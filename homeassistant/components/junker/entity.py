"""Base entity for the Junker integration."""

from typing import override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_AREA_ID, CONF_MUNICIPALITY, CONF_WASTE_TYPES, DOMAIN
from .coordinator import JunkerConfigEntry, JunkerDataUpdateCoordinator
from .junker_api import Collection


class JunkerEntity(CoordinatorEntity[JunkerDataUpdateCoordinator]):
    """Base class for Junker entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JunkerDataUpdateCoordinator,
        entry: JunkerConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        area_id = entry.data.get(CONF_AREA_ID, "all")
        self._identifier = f"{entry.data[CONF_MUNICIPALITY].casefold()}:{area_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._identifier)},
            manufacturer="Junker",
            name=entry.title,
        )

    @property
    def collections(self) -> list[Collection]:
        """Return the selected collections, renamed and without today's."""
        names = self._entry.options.get(CONF_WASTE_TYPES, {})
        today = dt_util.now().date()
        return [
            Collection(collection.date, names[collection.waste_type])
            for collection in self.coordinator.data
            if collection.waste_type in names and collection.date != today
        ]

    @override
    async def async_added_to_hass(self) -> None:
        """Refresh the state every midnight."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=0, second=5
            )
        )

    @callback
    def _async_midnight(self, _: object) -> None:
        """Write the state after midnight."""
        self.async_write_ha_state()
