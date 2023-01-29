"""Class definitions for OneTracker Parcel Entity."""
from __future__ import annotations

from datetime import datetime

from homeassistant.core import callback
from homeassistant.components.sensor import RestoreEntity, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OneTrackerDataUpdateCoordinator
from .api_responses import Parcel, TrackingEvent

import logging

_LOGGER = logging.getLogger(__name__)


class ParcelEntity(CoordinatorEntity, SensorEntity):
    """A class definition for OneTracker parcel data."""

    _attr_icon = "mdi:package"

    id: int
    user_id: int
    email_id: int
    email_sender: str
    retailer_name: str
    _description: str
    notification_level: int
    is_archived: bool
    carrier: str
    carrier_name: str
    carrier_redirection_available: bool
    tracker_cached: bool
    _tracking_id: str
    tracking_url: str | None = None
    tracking_status: str
    tracking_status_description: str
    tracking_status_text: str
    tracking_extra_info: str
    tracking_location: str
    tracking_time_estimated: datetime | None = None
    tracking_time_delivered: datetime | None = None
    tracking_lock: bool
    tracking_events: list[TrackingEvent] | None = None
    time_added: datetime
    time_updated: datetime

    def __init__(
        self, coordinator: OneTrackerDataUpdateCoordinator, parcel: Parcel
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        _LOGGER.warning("Setup parcel entity: %s", parcel.id)
        super().__init__(coordinator, context=parcel.id)
        self.id = parcel.id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.warning("Handle Coordinator Update")
        self.async_write_ha_state()

    # @property
    # def extra_state_attributes(self):
    #     """Return entity specific state attributes."""
    #     return self._attributes

    @property
    def name(self):
        """Return the name."""
        if not (name := self._description):
            name = self._tracking_id
        return name
