"""Sensor for Hyundai / Kia Connect integration."""
import logging

from .const import DOMAIN
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_devices([HyundaiKiaConnectSensor(coordinator, config_entry)])


class HyundaiKiaConnectSensor(HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect sensor class."""

    @property
    def name(self):
        """Return a name to use for this sensor."""
        return f"{self.coordinator.data.name}_odometer"

    @property
    def state(self):
        """Return the state to use for this sensor."""
        return self.coordinator.data.odometer
