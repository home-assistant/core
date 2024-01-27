"""Support for MotionMount binary sensors."""
import motionmount

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MotionMountMovingSensor(mm, entry)])


class MotionMountMovingSensor(MotionMountEntity, BinarySensorEntity):
    """The moving sensor of a MotionMount."""

    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_translation_key = "motionmount_is_moving"

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize moving binary sensor entity."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-moving"

    @property
    def is_on(self) -> bool:
        """Get on status."""
        return self.mm.is_moving or False
