"""Support for the GPSLogger device tracking."""
import logging

from homeassistant.components.device_tracker import (
    ATTR_ATTRIBUTES, ATTR_BATTERY, DEFAULT_GPS_ACCURACY, SOURCE_TYPE_GPS,
    DeviceTrackerEntity)
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_KEY, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)

GPSLOGGER_ENTITIES = 'gpslogger_entities'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up gpslogger from config entry."""
    entities = hass.data.setdefault(GPSLOGGER_ENTITIES, {})

    async def async_see(
            device, latitude, longitude, battery, accuracy, attributes):
        """Notify the device tracker entities that you see a device."""
        entity = entities.get(device)

        if entity:
            await entity.async_seen(
                latitude=latitude, longitude=longitude,
                battery=battery, accuracy=accuracy, attributes=attributes)
            return

        # If no device can be found, create it
        entity = GPSLoggerEntity(
            device, latitude, longitude, battery, accuracy, attributes)
        entities[device] = entity
        async_add_entities([entity])

    hass.data[DATA_KEY] = async_dispatcher_connect(
        hass, TRACKER_UPDATE, async_see
    )
    return True


class GPSLoggerEntity(DeviceTrackerEntity):
    """Represent a tracked device."""

    def __init__(
            self, device, latitude, longitude, battery, accuracy, attributes):
        """Set up Geofency entity."""
        self._accuracy = accuracy
        self._attributes = attributes
        self._name = device
        self._battery = battery
        self._latitude = latitude
        self._longitude = longitude
        self._connected_seen = None

    @property
    def battery(self):
        """Return battery value of the device."""
        return self._battery

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def gps_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._longitude

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._connected_seen = self._async_seen

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._connected_seen = None
        self.hass.data[GPSLOGGER_ENTITIES].pop(self._name)

    async def async_seen(self, **kwargs):
        """Mark the device as seen."""
        if self._connected_seen is None:
            return
        await self._connected_seen(**kwargs)

    async def _async_seen(self, **kwargs):
        """Mark the device as seen."""
        self._attributes.update(kwargs.get(ATTR_ATTRIBUTES, {}))
        self._battery = kwargs.get(ATTR_BATTERY)
        self._latitude = kwargs.get(ATTR_LATITUDE)
        self._longitude = kwargs.get(ATTR_LONGITUDE)
        self._accuracy = kwargs.get(ATTR_GPS_ACCURACY, DEFAULT_GPS_ACCURACY)

        await self.async_update_ha_state()
