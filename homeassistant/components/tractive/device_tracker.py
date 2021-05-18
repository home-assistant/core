"""Support for Tractive device trackers."""

import asyncio
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id]
    trackables = await client.trackable_objects()

    # TODO: use concurrency
    entities = await asyncio.gather(
        *[create_trackable_entity(client, trackable) for trackable in trackables]
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
        client, trackable, tracker_details, hw_info, pos_report
    )


class TractiveDeviceTracker(TrackerEntity):
    """Tractive device tracker."""

    def __init__(self, client, trackable, tracker_details, hw_info, pos_report):
        """Initialize tracker entity."""
        self._client = client
        self._trackable = trackable
        self._tracker_details = tracker_details
        self._hw_info = hw_info

        self._battery_level = hw_info["battery_level"]
        self._latitude = pos_report["latlong"][0]
        self._longitude = pos_report["latlong"][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        pet_name = self._trackable["details"]["name"]
        device_id = self._trackable["device_id"]
        return f"{device_id} {pet_name}"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return self._trackable["_id"]

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:paw"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._longitude

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._battery_level
