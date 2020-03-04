"""Support for tracking Tesla cars."""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    entities = [
        TeslaDeviceEntity(
            device,
            hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"],
            config_entry,
        )
        for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"][
            "devices_tracker"
        ]
    ]
    async_add_entities(entities, True)


class TeslaDeviceEntity(TeslaDevice, TrackerEntity):
    """A class representing a Tesla device."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialize the Tesla device scanner."""
        super().__init__(tesla_device, controller, config_entry)
        self._latitude = None
        self._longitude = None
        self._attributes = {"trackr_id": self.unique_id}
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
                "heading": location["heading"],
                "speed": location["speed"],
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
        """Return whether polling is needed."""
        return True

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def force_update(self):
        """All updates do not need to be written to the state machine."""
        return False
