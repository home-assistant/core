"""Support for MotionMount sensors."""

from typing import Final

import motionmount
from motionmount import MotionMountSystemError

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MotionMountConfigEntry
from .entity import MotionMountEntity

PARALLEL_UPDATES = 0

ERROR_MESSAGES: Final = {
    MotionMountSystemError.MotorError: "motor",
    MotionMountSystemError.ObstructionDetected: "obstruction",
    MotionMountSystemError.TVWidthConstraintError: "tv_width_constraint",
    MotionMountSystemError.HDMICECError: "hdmi_cec",
    MotionMountSystemError.InternalError: "internal",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MotionMountConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

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

        for error, message in ERROR_MESSAGES.items():
            if error in status:
                return message

        return "none"
