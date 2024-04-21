"""Define a base ReCollect Waste entity."""

from aiorecollect.client import PickupEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN


class ReCollectWasteEntity(CoordinatorEntity[DataUpdateCoordinator[list[PickupEvent]]]):
    """Define a base ReCollect Waste entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[PickupEvent]],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._identifier = f"{entry.data[CONF_PLACE_ID]}_{entry.data[CONF_SERVICE_ID]}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._identifier)},
            manufacturer="ReCollect Waste",
            name="ReCollect Waste",
        )
        self._attr_extra_state_attributes = {}
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
