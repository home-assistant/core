"""Support for MotionMount sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MotionMountMovingSensor(coordinator, entry.entry_id)])


class MotionMountMovingSensor(MotionMountEntity, BinarySensorEntity):
    """The moving sensor of a MotionMount."""

    _attr_name = "Moving"
    _attr_device_class = BinarySensorDeviceClass.MOVING

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-moving"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.coordinator.data["is_moving"]
        self.async_write_ha_state()
