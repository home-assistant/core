"""Support for Tractive device trackers."""

import asyncio
import logging

from homeassistant.components.device_tracker import (
    SOURCE_TYPE_BLUETOOTH,
    SOURCE_TYPE_GPS,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKER_HARDWARE_STATUS_UPDATED,
    TRACKER_POSITION_UPDATED,
)
from .entity import TractiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id]

    trackables = await client.trackable_objects()

    entities = await asyncio.gather(
        *(create_trackable_entity(client, trackable) for trackable in trackables)
    )

    async_add_entities(entities)


async def create_trackable_entity(client, trackable):
    """Create an entity instance."""
    trackable = await trackable.details()
    tracker = client.tracker(trackable["device_id"])

    tracker_details, hw_info, pos_report = await asyncio.gather(
        tracker.details(), tracker.hw_info(), tracker.pos_report()
    )

    return TractiveDeviceTracker(
        client.user_id, trackable, tracker_details, hw_info, pos_report
    )


class TractiveDeviceTracker(TractiveEntity, TrackerEntity):
    """Tractive device tracker."""

    _attr_icon = "mdi:paw"

    def __init__(self, user_id, trackable, tracker_details, hw_info, pos_report):
        """Initialize tracker entity."""
        super().__init__(user_id, trackable, tracker_details)

        self._battery_level = hw_info["battery_level"]
        self._latitude = pos_report["latlong"][0]
        self._longitude = pos_report["latlong"][1]
        self._accuracy = pos_report["pos_uncertainty"]
        self._source_type = pos_report["sensor_used"]

        self._attr_name = f"{self._tracker_id} {trackable['details']['name']}"
        self._attr_unique_id = trackable["_id"]

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        if self._source_type == "GPS":
            return SOURCE_TYPE_GPS
        if self._source_type == "PHONE":
            return SOURCE_TYPE_BLUETOOTH
        return None

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._longitude

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._battery_level

    @callback
    def _handle_hardware_status_update(self, event):
        self._battery_level = event["battery_level"]
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def _handle_position_update(self, event):
        self._latitude = event["latitude"]
        self._longitude = event["longitude"]
        self._accuracy = event["accuracy"]
        self._source_type = event["sensor_used"]
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def _handle_server_unavailable(self):
        self._latitude = None
        self._longitude = None
        self._accuracy = None
        self._battery_level = None
        self._source_type = None
        self._attr_available = False
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_HARDWARE_STATUS_UPDATED}-{self._tracker_id}",
                self._handle_hardware_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_POSITION_UPDATED}-{self._tracker_id}",
                self._handle_position_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self._handle_server_unavailable,
            )
        )
