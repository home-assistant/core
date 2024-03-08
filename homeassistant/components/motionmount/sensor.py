"""Support for MotionMount sensors."""
import motionmount

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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

    async_add_entities((MotionMountErrorStatusSensor(mm, entry),))


class MotionMountErrorStatusSensor(MotionMountEntity, SensorEntity):
    """The error status sensor of a MotionMount."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["none", "motor", "internal"]
    _attr_translation_key = "motionmount_error_status"

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize sensor entiry."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-error-status"

    @property
    def native_value(self) -> str:
        """Return error status."""
        errors = self.mm.error_status or 0

        if errors & (1 << 31):
            # Only when but 31 is set are there any errors active at this moment
            if errors & (1 << 10):
                return "motor"

            return "internal"

        return "none"
