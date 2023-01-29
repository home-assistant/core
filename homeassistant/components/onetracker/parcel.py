"""Class definitions for OneTracker Parcel Entity."""
from __future__ import annotations


from homeassistant.core import callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OneTrackerDataUpdateCoordinator
from .api_responses import Parcel

import logging

_LOGGER = logging.getLogger(__name__)


class ParcelEntity(CoordinatorEntity, SensorEntity):
    """A class definition for OneTracker parcel data."""

    _attr_icon = "mdi:package"
    coordinator: OneTrackerDataUpdateCoordinator
    parcel: Parcel

    def __init__(
        self, coordinator: OneTrackerDataUpdateCoordinator, parcel: Parcel
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=parcel.id)

        self._attr_unique_id = f"{parcel.id}-onetracker"
        self.id = parcel.id
        self.parcel = parcel
        self._attr_native_value = parcel.tracking_status
        self._attr_should_poll = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # _LOGGER.warning("Handle Coordinator Update")
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "tracking_id": self.parcel.tracking_id,
            "tracking_status_readable": self.parcel.tracking_status_readable,
            "tracking_status_description": self.parcel.tracking_status_description,
            "tracking_location": self.parcel.tracking_location,
            "tracking_time_estimated": self.parcel.tracking_time_estimated,
            "tracking_time_delivered": self.parcel.tracking_time_delivered,
            "time_updated": self.parcel.time_updated,
            "carrier": self.parcel.carrier,
            "carrier_name": self.parcel.carrier_name,
        }

    @property
    def name(self):
        """Return the name."""
        if not (name := self.parcel.description):
            name = self.parcel.tracking_id
        return name

    async def async_update(self) -> None:
        _LOGGER.warning("Async update: %s", self.unique_id)
        self.parcel = await self.coordinator.api.get_parcel(self.parcel.id)
