"""Device tracker platform that adds support for OwnTracks over MQTT."""
import logging

from homeassistant.core import callback
from homeassistant.components.device_tracker.const import ENTITY_ID_FORMAT
from homeassistant.components.device_tracker.config_entry import (
    DeviceTrackerEntity
)
from . import DOMAIN as OT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OwnTracks based off an entry."""
    @callback
    def _receive_data(dev_id, host_name, gps, attributes, gps_accuracy=None,
                      battery=None, source_type=None, location_name=None):
        """Receive set location."""
        device = hass.data[OT_DOMAIN]['devices'].get(dev_id)

        if device is not None:
            device.update_data(
                host_name=host_name,
                gps=gps,
                attributes=attributes,
                gps_accuracy=gps_accuracy,
                battery=battery,
                source_type=source_type,
                location_name=location_name,
            )
            return

        device = hass.data[OT_DOMAIN]['devices'][dev_id] = OwnTracksEntity(
            dev_id=dev_id,
            host_name=host_name,
            gps=gps,
            attributes=attributes,
            gps_accuracy=gps_accuracy,
            battery=battery,
            source_type=source_type,
            location_name=location_name,
        )
        async_add_entities([device])

    hass.data[OT_DOMAIN]['context'].async_see = _receive_data
    return True


class OwnTracksEntity(DeviceTrackerEntity):
    """Represent a tracked device."""

    def __init__(self, dev_id, host_name, gps, attributes, gps_accuracy,
                 battery, source_type, location_name):
        """Set up OwnTracks entity."""
        self._dev_id = dev_id
        self._host_name = host_name
        self._gps = gps
        self._gps_accuracy = gps_accuracy
        self._location_name = location_name
        self._attributes = attributes
        self._battery = battery
        self._source_type = source_type
        self.entity_id = ENTITY_ID_FORMAT.format(dev_id)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._dev_id

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._battery

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._gps_accuracy

    @property
    def latitude(self):
        """Return latitude value of the device."""
        if self._gps is not None:
            return self._gps[0]

        return None

    @property
    def longitude(self):
        """Return longitude value of the device."""
        if self._gps is not None:
            return self._gps[1]

        return None

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def name(self):
        """Return the name of the device."""
        return self._host_name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return self._source_type

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'name': self._host_name,
            'identifiers': {(OT_DOMAIN, self._dev_id)},
        }

    @callback
    def update_data(self, host_name, gps, attributes, gps_accuracy,
                    battery, source_type, location_name):
        """Mark the device as seen."""
        self._host_name = host_name
        self._gps = gps
        self._gps_accuracy = gps_accuracy
        self._location_name = location_name
        self._attributes = attributes
        self._battery = battery
        self._source_type = source_type

        self.async_write_ha_state()
