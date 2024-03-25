"""Support for Denon AVR additional sensors."""

from typing import Any

from denonavr import DenonAVR
from denonavr.const import POWER_ON

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import StateType

from .device import DenonDeviceEntity

ATTR_ZONE = "zone"

SENSOR_BASS = "bass"
SENSOR_BASS_LEVEL = "bass_level"
SENSOR_DYNAMIC_EQ = "dynamic_eq"
SENSOR_DYNAMIC_VOLUME = "dynamic_volume"
SENSOR_MULTI_EQ = "multi_eq"
SENSOR_REFERENCE_LEVEL_OFFSET = "reference_level_offset"
SENSOR_TONE_CONTROL_ADJUST = "tone_control_adjust"
SENSOR_TONE_CONTROL_STATUS = "tone_control_status"
SENSOR_TREBLE = "treble"
SENSOR_TREBLE_LEVEL = "treble_level"

SENSOR_ENTITIES = {
    SENSOR_BASS: "Bass",
    SENSOR_BASS_LEVEL: "Bass Level",
    SENSOR_DYNAMIC_EQ: "Dynamic EQ",
    SENSOR_DYNAMIC_VOLUME: "Dynamic Volume",
    SENSOR_MULTI_EQ: "Multi EQ",
    SENSOR_REFERENCE_LEVEL_OFFSET: "Reference Level Offset",
    SENSOR_TONE_CONTROL_ADJUST: "Tone Control Adjust",
    SENSOR_TONE_CONTROL_STATUS: "Tone Control Status",
    SENSOR_TREBLE: "Treble",
    SENSOR_TREBLE_LEVEL: "Treble Level",
}


class DenonSensor(DenonDeviceEntity, SensorEntity):
    """Representation of a Denon Sensor Device."""

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: ConfigEntry,
        attribute: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(receiver, unique_id, config_entry)

        self._attribute = attribute

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {ATTR_ZONE: getattr(self._receiver, ATTR_ZONE, None)}

    @property
    def name(self) -> str:
        """Name of the entity."""
        return SENSOR_ENTITIES.get(self._attribute, self._attribute)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        receiver = self._receiver

        if receiver.power != POWER_ON:
            return None

        return getattr(receiver, self._attribute, None)
