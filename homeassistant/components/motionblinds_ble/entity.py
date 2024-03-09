"""Base entity for the Motionblinds BLE integration."""

from motionblindsble.device import MotionDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_BLIND_TYPE, MANUFACTURER


class MotionblindsBLEEntity(Entity):
    """Base class for Motionblinds BLE entities."""

    _attr_has_entity_name = True

    _device: MotionDevice
    config_entry: ConfigEntry

    def __init__(self, device: MotionDevice, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._device = device
        self.config_entry = entry
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=entry.data[CONF_BLIND_TYPE],
            name=device.display_name,
        )
