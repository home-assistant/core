"""Support for MotionMount sensors."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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

    async_add_entities(
        [
            MotionMountErrorStatusSensor(coordinator, entry.entry_id),
        ]
    )


class MotionMountErrorStatusSensor(MotionMountEntity, SensorEntity):
    """The error status sensor of a MotionMount."""

    _attr_name = "Error Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["None", "Motor", "Internal"]

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-error-status"

    @callback
    def _handle_coordinator_update(self) -> None:
        errors = self.coordinator.data["error_status"]

        if errors & (1 << 31):
            # Only when but 31 is set are there any errors active at this moment
            if errors & (1 << 10):
                self._attr_native_value = "Motor"
            else:
                self._attr_native_value = "Internal"
        else:
            self._attr_native_value = "None"
        self.async_write_ha_state()
