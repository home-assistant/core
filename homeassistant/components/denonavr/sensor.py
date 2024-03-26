"""Support for Denon AVR additional sensors."""

import logging

from denonavr import DenonAVR
from denonavr.const import POWER_ON

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import CONF_RECEIVER
from .config_flow import CONF_SERIAL_NUMBER, DOMAIN
from .entity import DenonDeviceEntity

_LOGGER = logging.getLogger(__name__)

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
    SENSOR_BASS,
    SENSOR_BASS_LEVEL,
    SENSOR_DYNAMIC_EQ,
    SENSOR_DYNAMIC_VOLUME,
    SENSOR_MULTI_EQ,
    SENSOR_REFERENCE_LEVEL_OFFSET,
    SENSOR_TONE_CONTROL_ADJUST,
    SENSOR_TONE_CONTROL_STATUS,
    SENSOR_TREBLE,
    SENSOR_TREBLE_LEVEL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DenonAVR sensors from a config entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    receiver = data[CONF_RECEIVER]
    if config_entry.data[CONF_SERIAL_NUMBER] is not None:
        unique_id = config_entry.unique_id
    else:
        unique_id = config_entry.entry_id
    for sensor in SENSOR_ENTITIES:
        sensor_unique_id = f"{unique_id}-{sensor}"
        entities.append(
            DenonSensor(
                receiver,
                sensor_unique_id,
                config_entry,
                sensor,
            )
        )
    _LOGGER.debug(
        "Sensor entities for %s receiver at host %s initialized",
        receiver.manufacturer,
        receiver.host,
    )

    async_add_entities(entities)


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
        self.translation_key = attribute

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        receiver = self._receiver

        if receiver.power != POWER_ON:
            return None

        return getattr(receiver, self._attribute, None)
