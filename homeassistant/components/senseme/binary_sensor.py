"""Support for Big Ass Fans SenseME occupancy sensor."""
from __future__ import annotations

from aiosenseme import SensemeDevice

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SensemeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME occupancy sensors."""
    device = hass.data[DOMAIN][entry.entry_id]
    if device.has_sensor:
        async_add_entities([HASensemeOccupancySensor(device)])


class HASensemeOccupancySensor(SensemeEntity, BinarySensorEntity):
    """Representation of a Big Ass Fans SenseME occupancy sensor."""

    def __init__(self, device: SensemeDevice) -> None:
        """Initialize the entity."""
        super().__init__(device, f"{device.name} Occupancy")
        self._attr_unique_id = f"{self._device.uuid}-SENSOR"
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.motion_detected
