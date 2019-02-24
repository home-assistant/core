"""Support for the Locative platform."""
import logging

from homeassistant.components.device_tracker import (
    ATTR_LOCATION_NAME, SOURCE_TYPE_GPS, DeviceTrackerEntity)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_KEY, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)

LOCATIVE_ENTITIES = 'locative_entities'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Locative from config entry."""
    entities = hass.data.setdefault(LOCATIVE_ENTITIES, {})

    async def async_see(device, latitude, longitude, location_name):
        """Notify the device tracker entities that you see a device."""
        entity = entities.get(device)

        if entity:
            await entity.async_seen(
                latitude=latitude, longitude=longitude,
                location_name=location_name)
            return

        # If no device can be found, create it
        entity = LocativeEntity(device, latitude, longitude, location_name)
        entities[device] = entity
        async_add_entities([entity])

    hass.data[DATA_KEY] = async_dispatcher_connect(
        hass, TRACKER_UPDATE, async_see
    )
    return True


class LocativeEntity(DeviceTrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device, latitude, longitude, location_name):
        """Set up Locative entity."""
        self._name = device
        self._location_name = location_name
        self._latitude = latitude
        self._longitude = longitude
        self._connected_seen = None

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._location_name

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
        self.hass.data[LOCATIVE_ENTITIES].pop(self._name)

    async def async_seen(self, **kwargs):
        """Mark the device as seen."""
        if self._connected_seen is None:
            return
        await self._connected_seen(**kwargs)

    async def _async_seen(self, **kwargs):
        """Mark the device as seen."""
        self._location_name = kwargs.get(ATTR_LOCATION_NAME)
        self._latitude = kwargs.get(ATTR_LATITUDE)
        self._longitude = kwargs.get(ATTR_LONGITUDE)

        await self.async_update_ha_state()
