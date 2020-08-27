"""Support for Flo Water Monitor binary sensors."""

from typing import List

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator
from .entity import FloEntity

DEPENDENCIES = ["flo"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    devices: List[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN]["devices"]
    entities = [FloPendingAlertsBinarySensor(device) for device in devices]
    async_add_entities(entities)


class FloPendingAlertsBinarySensor(FloEntity, BinarySensorEntity):
    """Binary sensor that reports on if there are any pending system alerts."""

    def __init__(self, device):
        """Initialize the pending alerts binary sensor."""
        super().__init__("pending_system_alerts", "Pending System Alerts", device)

    @property
    def is_on(self):
        """Return true if the Flo device has pending alerts."""
        return self._device.has_alerts

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self._device.has_alerts:
            attr["info"] = self._device.pending_info_alerts_count
            attr["warning"] = self._device.pending_warning_alerts_count
            attr["critical"] = self._device.pending_critical_alerts_count
        return attr

    @property
    def device_class(self):
        """Return the device class for the binary sensor."""
        return DEVICE_CLASS_PROBLEM
