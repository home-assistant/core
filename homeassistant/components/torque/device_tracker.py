"""
Device Tracker
"""
from calendar import c
import logging
from typing import Optional

from attr import NOTHING

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .torque_entity import TorqueEntity

from .const import (
    DOMAIN,
    PID_GPS_LATITUDE,
    PID_GPS_LONGITUDE,
    PID_GPS_ACCURACY,
    PID_GPS_ALTITUDE,
    PID_GPS_SATELLITES,
    PID_GPS_BEARING
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the device tracker by config_entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()


    sensor = TorqueDeviceTracker(hass, coordinator, 
    coordinator.id, 
    "", 
    coordinator.vehicle_name + " Tracker", 
    "", 
    "mdi:car-select")

    async_add_entities([sensor], True)

    await coordinator.async_config_entry_first_refresh()


class TorqueDeviceTracker(TorqueEntity, TrackerEntity, RestoreEntity):
    """Representation of a Sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data:
            self.async_write_ha_state()

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of the device."""
        latitude = None
        if self.coordinator.data:
            if PID_GPS_LATITUDE in self.coordinator.data.keys():
                latitude = self.coordinator.data[PID_GPS_LATITUDE]
        return latitude

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of the device."""
        longitude = None
        if self.coordinator.data:
            if PID_GPS_LONGITUDE in self.coordinator.data.keys():
                longitude = self.coordinator.data[PID_GPS_LONGITUDE]
        return longitude

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        location_accuracy = None
        if self.coordinator.data:
            if PID_GPS_ACCURACY in self.coordinator.data.keys():
                location_accuracy = self.coordinator.data[PID_GPS_ACCURACY]
        return location_accuracy

    @property
    def altitude(self) -> int:
        """Return the location accuracy of the device."""
        altitude = None
        if self.coordinator.data:
            if PID_GPS_ALTITUDE in self.coordinator.data.keys():
                altitude = self.coordinator.data[PID_GPS_ALTITUDE]
        return altitude

    @property
    def satellites(self) -> int:
        """Return the location accuracy of the device."""
        sattelites = None
        if self.coordinator.data:
            if PID_GPS_SATELLITES in self.coordinator.data.keys():
                sattelites = self.coordinator.data[PID_GPS_SATELLITES]
        return sattelites

    @property
    def bearing(self) -> int:
        """Return the location accuracy of the device."""
        bearing = None
        if self.coordinator.data:
            if PID_GPS_BEARING in self.coordinator.data.keys():
                bearing = self.coordinator.data[PID_GPS_BEARING]
        return bearing

    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {}
        attr.update(super().state_attributes)

        if self.latitude is not None and self.longitude is not None:
            attr[ATTR_LATITUDE] = self.latitude
            attr[ATTR_LONGITUDE] = self.longitude
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy
            attr['altitude'] = self.altitude
            attr['satellites'] = self.satellites
            attr['bearing'] = self.bearing

        return attr

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @ property
    def device_class(self):
        return None
