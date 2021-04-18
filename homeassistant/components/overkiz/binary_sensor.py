"""Support for Overkiz binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DOMAIN as BINARY_SENSOR,
    BinarySensorEntity,
)

from .const import DOMAIN
from .overkiz_entity import OverkizEntity

CORE_ASSEMBLY_STATE = "core:AssemblyState"
CORE_BUTTON_STATE = "core:ButtonState"
CORE_CONTACT_STATE = "core:ContactState"
CORE_GAS_DETECTION_STATE = "core:GasDetectionState"
CORE_OCCUPANCY_STATE = "core:OccupancyState"
CORE_OPENING_STATE = "core:OpeningState"
CORE_OPEN_CLOSED_TILT_STATE = "core:OpenClosedTiltState"
CORE_RAIN_STATE = "core:RainState"
CORE_SMOKE_STATE = "core:SmokeState"
CORE_THREE_WAY_HANDLE_DIRECTION_STATE = "core:ThreeWayHandleDirectionState"
CORE_VIBRATION_STATE = "core:VibrationState"
CORE_WATER_DETECTION_STATE = "core:WaterDetectionState"

IO_VIBRATION_DETECTED_STATE = "io:VibrationDetectedState"

STATE_OPEN = "open"
STATE_PERSON_INSIDE = "personInside"
STATE_DETECTED = "detected"
STATE_PRESSED = "pressed"

OVERKIZ_BINARY_SENSOR_DEVICE_CLASSES = {
    "AirFlowSensor": DEVICE_CLASS_GAS,
    "CarButtonSensor": None,
    "ContactSensor": DEVICE_CLASS_OPENING,
    "MotionSensor": DEVICE_CLASS_MOTION,
    "OccupancySensor": DEVICE_CLASS_OCCUPANCY,
    "RainSensor": DEVICE_CLASS_MOISTURE,
    "SirenStatus": DEVICE_CLASS_OPENING,
    "SmokeSensor": DEVICE_CLASS_SMOKE,
    "WaterDetectionSensor": DEVICE_CLASS_MOISTURE,
    "WaterSensor": DEVICE_CLASS_MOISTURE,
    "WindowHandle": DEVICE_CLASS_OPENING,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Overkiz sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        OverkizBinarySensor(device.deviceurl, coordinator)
        for device in data["platforms"][BINARY_SENSOR]
    ]
    async_add_entities(entities)


class OverkizBinarySensor(OverkizEntity, BinarySensorEntity):
    """Representation of a Overkiz Binary Sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""

        return (
            self.executor.select_state(
                CORE_ASSEMBLY_STATE,
                CORE_BUTTON_STATE,
                CORE_CONTACT_STATE,
                CORE_GAS_DETECTION_STATE,
                CORE_OCCUPANCY_STATE,
                CORE_OPENING_STATE,
                CORE_OPEN_CLOSED_TILT_STATE,
                CORE_RAIN_STATE,
                CORE_SMOKE_STATE,
                CORE_THREE_WAY_HANDLE_DIRECTION_STATE,
                CORE_VIBRATION_STATE,
                CORE_WATER_DETECTION_STATE,
                IO_VIBRATION_DETECTED_STATE,
            )
            in [STATE_OPEN, STATE_PERSON_INSIDE, STATE_DETECTED, STATE_PRESSED]
        )

    @property
    def device_class(self):
        """Return the class of the device."""
        return OVERKIZ_BINARY_SENSOR_DEVICE_CLASSES.get(
            self.device.widget
        ) or OVERKIZ_BINARY_SENSOR_DEVICE_CLASSES.get(self.device.ui_class)
