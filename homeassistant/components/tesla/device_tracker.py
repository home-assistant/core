"""Support for tracking Tesla cars."""
import logging

from homeassistant.util import slugify

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Tesla binary_sensors by config_entry."""
    devices = [
        TeslaDeviceEntity(
            device,
            hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"],
            config_entry,
        )
        for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"][
            "devices_tracker"
        ]
    ]
    async_add_devices(devices, True)


class TeslaDeviceEntity(TrackerEntity, TeslaDevice):
    """A class representing a Tesla device."""

    def __init__(self, tesla_device, controller, config_entry=None):
        """Initialize the Tesla device scanner."""
        super().__init__(tesla_device, controller, config_entry)
        self._unique_id = slugify(self.tesla_device.uniq_name)
        self._latitude = None
        self._longitude = None
        self._attributes = {
            "trackr_id": self.unique_id,
            "id": self.unique_id,
            "name": self.name,
        }
        self._listener = None

    async def async_update(self):
        """Update the device info."""
        _LOGGER.debug("Updating device position: %s", self.name)
        await super().async_update()
        location = self.tesla_device.get_location()
        if location:
            self._latitude = location["latitude"]
            self._longitude = location["longitude"]
            self._attributes = {
                "trackr_id": self.unique_id,
                "id": self.unique_id,
                "name": self.name,
                "gps": (self.latitude, self.longitude),
                "heading": location["heading"],
                "speed": location["speed"],
                "source_type": self.source_type,
            }

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS
