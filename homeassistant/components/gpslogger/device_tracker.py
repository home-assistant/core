"""Support for the GPSLogger device tracking."""
import logging

from homeassistant.core import callback
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import (
    DeviceTrackerEntity
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as GPL_DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, entry,
                            async_add_entities):
    """Configure a dispatcher connection based on a config entry."""
    @callback
    def _receive_data(device, gps, battery, accuracy, attrs):
        """Receive set location."""
        if device in hass.data[GPL_DOMAIN]['devices']:
            return

        hass.data[GPL_DOMAIN]['devices'].add(device)

        async_add_entities([GPSLoggerEntity(
            device, gps, battery, accuracy, attrs
        )])

    hass.data[GPL_DOMAIN]['unsub_device_tracker'][entry.entry_id] = \
        async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)


class GPSLoggerEntity(DeviceTrackerEntity):
    """Represent a tracked device."""

    def __init__(
            self, device, location, battery, accuracy, attributes):
        """Set up Geofency entity."""
        self._accuracy = accuracy
        self._attributes = attributes
        self._name = device
        self._battery = battery
        self._location = location
        self._unsub_dispatcher = None
        self._unique_id = device

    @property
    def battery_level(self):
        """Return battery value of the device."""
        return self._battery

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._location[0]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._location[1]

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'name': self._name,
            'identifiers': {(GPL_DOMAIN, self._unique_id)},
        }

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data)

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, device, location, battery, accuracy,
                            attributes):
        """Mark the device as seen."""
        if device != self.name:
            return

        self._location = location
        self._battery = battery
        self._accuracy = accuracy
        self._attributes.update(attributes)
        self.async_write_ha_state()
