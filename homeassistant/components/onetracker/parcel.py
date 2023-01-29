"""Class definitions for OneTracker Parcel Entity."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_responses import Parcel
from .const import (
    ATTR_CARRIER,
    ATTR_CARRIER_NAME,
    ATTR_TIME_UPDATED,
    ATTR_TRACKING_ID,
    ATTR_TRACKING_LOCATION,
    ATTR_TRACKING_STATUS_DESCRIPTION,
    ATTR_TRACKING_STATUS_READABLE,
    ATTR_TRACKING_TIME_DELIVERED,
    ATTR_TRACKING_TIME_ESTIMATED,
)
from .coordinator import OneTrackerDataUpdateCoordinator


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
            ATTR_CARRIER: self.parcel.carrier,
            ATTR_CARRIER_NAME: self.parcel.carrier_name,
            ATTR_TIME_UPDATED: self.parcel.time_updated,
            ATTR_TRACKING_ID: self.parcel.tracking_id,
            ATTR_TRACKING_STATUS_READABLE: self.parcel.tracking_status_readable,
            ATTR_TRACKING_STATUS_DESCRIPTION: self.parcel.tracking_status_description,
            ATTR_TRACKING_LOCATION: self.parcel.tracking_location,
            ATTR_TRACKING_TIME_ESTIMATED: self.parcel.tracking_time_estimated,
            ATTR_TRACKING_TIME_DELIVERED: self.parcel.tracking_time_delivered,
        }

    @property
    def name(self):
        """Return the name."""
        if not (name := self.parcel.description):
            name = self.parcel.tracking_id
        return name
