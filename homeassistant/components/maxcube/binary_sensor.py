"""Support for MAX! binary sensors via MAX! Cube."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_KEY, MaxCubeDeviceUpdater


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up a binary sensor for maxcube."""
    devices: list[MaxCubeBinarySensorBase] = []
    for handler in hass.data[DATA_KEY].values():
        for device in handler.cube.devices:
            devices.append(MaxCubeBattery(hass, config_entry, handler, device))
            # Only add Window Shutters
            if device.is_windowshutter():
                devices.append(MaxCubeShutter(hass, config_entry, handler, device))

    if devices:
        async_add_devices(devices)


class MaxCubeBinarySensorBase(BinarySensorEntity):
    """Base class for maxcube binary sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        self._cubehandle = handler
        self._device = device
        self._room = handler.cube.room_by_id(device.room_id)
        self.device_updater = MaxCubeDeviceUpdater(hass, config_entry, self._room, device)

    def update(self) -> None:
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()
        self.device_updater.update_device(self.entity_id)


class MaxCubeShutter(MaxCubeBinarySensorBase):
    """Representation of a MAX! Cube Binary Sensor device."""

    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        super().__init__(hass, config_entry, handler, device)

        self._attr_name = f"{self._room.name} {self._device.name}"
        self._attr_unique_id = self._device.serial

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._device.is_open


class MaxCubeBattery(MaxCubeBinarySensorBase):
    """Representation of a MAX! Cube Binary Sensor device."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        super().__init__(hass, config_entry, handler, device)

        self._attr_name = f"{self._room.name} {device.name} battery"
        self._attr_unique_id = f"{self._device.serial}_battery"

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._device.battery == 1
