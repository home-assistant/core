"""Support for MotionMount sensors."""

import motionmount

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MotionMountConfigEntry
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MotionMountConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm = entry.runtime_data

    async_add_entities((MotionMountErrorStatusSensor(mm, entry),))


class MotionMountErrorStatusSensor(MotionMountEntity, SensorEntity):
    """The error status sensor of a MotionMount."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "none",
        "motor",
        "hdmi_cec",
        "obstruction",
        "tv_width_constraint",
        "internal",
    ]
    _attr_translation_key = "motionmount_error_status"

    def __init__(
        self, mm: motionmount.MotionMount, config_entry: MotionMountConfigEntry
    ) -> None:
        """Initialize sensor entiry."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-error-status"

    @property
    def native_value(self) -> str:
        """Return error status."""
        status = self.mm.system_status

        if motionmount.MotionMountSystemError.MotorError in status:
            return "motor"
        if motionmount.MotionMountSystemError.ObstructionDetected in status:
            return "obstruction"
        if motionmount.MotionMountSystemError.TVWidthConstraintError in status:
            return "tv_width_constraint"
        if motionmount.MotionMountSystemError.HDMICECError in status:
            return "hdmi_cec"
        if motionmount.MotionMountSystemError.InternalError in status:
            return "internal"
        return "none"
