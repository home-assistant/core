"""Support for HomematicIP Cloud binary sensor."""
import logging
from typing import Any, Dict

from homematicip.aio.device import (
    AsyncAccelerationSensor,
    AsyncContactInterface,
    AsyncDevice,
    AsyncFullFlushContactInterface,
    AsyncMotionDetectorIndoor,
    AsyncMotionDetectorOutdoor,
    AsyncMotionDetectorPushButton,
    AsyncPluggableMainsFailureSurveillance,
    AsyncPresenceDetectorIndoor,
    AsyncRotaryHandleSensor,
    AsyncShutterContact,
    AsyncShutterContactMagnetic,
    AsyncSmokeDetector,
    AsyncWaterSensor,
    AsyncWeatherSensor,
    AsyncWeatherSensorPlus,
    AsyncWeatherSensorPro,
)
from homematicip.aio.group import AsyncSecurityGroup, AsyncSecurityZoneGroup
from homematicip.base.enums import SmokeDetectorAlarmType, WindowState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_MOVING,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    BinarySensorDevice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericDevice
from .hap import HomematicipHAP

_LOGGER = logging.getLogger(__name__)

ATTR_ACCELERATION_SENSOR_MODE = "acceleration_sensor_mode"
ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION = "acceleration_sensor_neutral_position"
ATTR_ACCELERATION_SENSOR_SENSITIVITY = "acceleration_sensor_sensitivity"
ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE = "acceleration_sensor_trigger_angle"
ATTR_MOISTURE_DETECTED = "moisture_detected"
ATTR_MOTION_DETECTED = "motion_detected"
ATTR_POWER_MAINS_FAILURE = "power_mains_failure"
ATTR_PRESENCE_DETECTED = "presence_detected"
ATTR_SMOKE_DETECTOR_ALARM = "smoke_detector_alarm"
ATTR_TODAY_SUNSHINE_DURATION = "today_sunshine_duration_in_minutes"
ATTR_WATER_LEVEL_DETECTED = "water_level_detected"
ATTR_WINDOW_STATE = "window_state"

GROUP_ATTRIBUTES = {
    "moistureDetected": ATTR_MOISTURE_DETECTED,
    "motionDetected": ATTR_MOTION_DETECTED,
    "powerMainsFailure": ATTR_POWER_MAINS_FAILURE,
    "presenceDetected": ATTR_PRESENCE_DETECTED,
    "waterlevelDetected": ATTR_WATER_LEVEL_DETECTED,
}

SAM_DEVICE_ATTRIBUTES = {
    "accelerationSensorNeutralPosition": ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION,
    "accelerationSensorMode": ATTR_ACCELERATION_SENSOR_MODE,
    "accelerationSensorSensitivity": ATTR_ACCELERATION_SENSOR_SENSITIVITY,
    "accelerationSensorTriggerAngle": ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE,
}


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP Cloud binary sensor from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.devices:
        if isinstance(device, AsyncAccelerationSensor):
            entities.append(HomematicipAccelerationSensor(hap, device))
        if isinstance(device, (AsyncContactInterface, AsyncFullFlushContactInterface)):
            entities.append(HomematicipContactInterface(hap, device))
        if isinstance(
            device,
            (AsyncShutterContact, AsyncShutterContactMagnetic, AsyncRotaryHandleSensor),
        ):
            entities.append(HomematicipShutterContact(hap, device))
        if isinstance(
            device,
            (
                AsyncMotionDetectorIndoor,
                AsyncMotionDetectorOutdoor,
                AsyncMotionDetectorPushButton,
            ),
        ):
            entities.append(HomematicipMotionDetector(hap, device))
        if isinstance(device, AsyncPluggableMainsFailureSurveillance):
            entities.append(
                HomematicipPluggableMainsFailureSurveillanceSensor(hap, device)
            )
        if isinstance(device, AsyncPresenceDetectorIndoor):
            entities.append(HomematicipPresenceDetector(hap, device))
        if isinstance(device, AsyncSmokeDetector):
            entities.append(HomematicipSmokeDetector(hap, device))
        if isinstance(device, AsyncWaterSensor):
            entities.append(HomematicipWaterDetector(hap, device))
        if isinstance(device, (AsyncWeatherSensorPlus, AsyncWeatherSensorPro)):
            entities.append(HomematicipRainSensor(hap, device))
        if isinstance(
            device, (AsyncWeatherSensor, AsyncWeatherSensorPlus, AsyncWeatherSensorPro)
        ):
            entities.append(HomematicipStormSensor(hap, device))
            entities.append(HomematicipSunshineSensor(hap, device))
        if isinstance(device, AsyncDevice) and device.lowBat is not None:
            entities.append(HomematicipBatterySensor(hap, device))

    for group in hap.home.groups:
        if isinstance(group, AsyncSecurityGroup):
            entities.append(HomematicipSecuritySensorGroup(hap, group))
        elif isinstance(group, AsyncSecurityZoneGroup):
            entities.append(HomematicipSecurityZoneSensorGroup(hap, group))

    if entities:
        async_add_entities(entities)


class HomematicipAccelerationSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud acceleration sensor."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOVING

    @property
    def is_on(self) -> bool:
        """Return true if acceleration is detected."""
        return self._device.accelerationSensorTriggered

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the acceleration sensor."""
        state_attr = super().device_state_attributes

        for attr, attr_key in SAM_DEVICE_ATTRIBUTES.items():
            attr_value = getattr(self._device, attr, None)
            if attr_value:
                state_attr[attr_key] = attr_value

        return state_attr


class HomematicipContactInterface(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud contact interface."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_OPENING

    @property
    def is_on(self) -> bool:
        """Return true if the contact interface is on/open."""
        if self._device.windowState is None:
            return None
        return self._device.windowState != WindowState.CLOSED


class HomematicipShutterContact(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud shutter contact."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the shutter contact is on/open."""
        if self._device.windowState is None:
            return None
        return self._device.windowState != WindowState.CLOSED


class HomematicipMotionDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud motion detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self._device.motionDetected


class HomematicipPresenceDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud presence detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_PRESENCE

    @property
    def is_on(self) -> bool:
        """Return true if presence is detected."""
        return self._device.presenceDetected


class HomematicipSmokeDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud smoke detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SMOKE

    @property
    def is_on(self) -> bool:
        """Return true if smoke is detected."""
        if self._device.smokeDetectorAlarmType:
            return (
                self._device.smokeDetectorAlarmType != SmokeDetectorAlarmType.IDLE_OFF
            )
        return False


class HomematicipWaterDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud water detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true, if moisture or waterlevel is detected."""
        return self._device.moistureDetected or self._device.waterlevelDetected


class HomematicipStormSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud storm sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize storm sensor."""
        super().__init__(hap, device, "Storm")

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:weather-windy" if self.is_on else "mdi:pinwheel-outline"

    @property
    def is_on(self) -> bool:
        """Return true, if storm is detected."""
        return self._device.storm


class HomematicipRainSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud rain sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize rain sensor."""
        super().__init__(hap, device, "Raining")

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true, if it is raining."""
        return self._device.raining


class HomematicipSunshineSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud sunshine sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize sunshine sensor."""
        super().__init__(hap, device, "Sunshine")

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_LIGHT

    @property
    def is_on(self) -> bool:
        """Return true if sun is shining."""
        return self._device.sunshine

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the illuminance sensor."""
        state_attr = super().device_state_attributes

        today_sunshine_duration = getattr(self._device, "todaySunshineDuration", None)
        if today_sunshine_duration:
            state_attr[ATTR_TODAY_SUNSHINE_DURATION] = today_sunshine_duration

        return state_attr


class HomematicipBatterySensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud low battery sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize battery sensor."""
        super().__init__(hap, device, "Battery")

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def is_on(self) -> bool:
        """Return true if battery is low."""
        return self._device.lowBat


class HomematicipPluggableMainsFailureSurveillanceSensor(
    HomematicipGenericDevice, BinarySensorDevice
):
    """Representation of a HomematicIP Cloud pluggable mains failure surveillance sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize pluggable mains failure surveillance sensor."""
        super().__init__(hap, device)

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_POWER

    @property
    def is_on(self) -> bool:
        """Return true if power mains fails."""
        return not self._device.powerMainsFailure


class HomematicipSecurityZoneSensorGroup(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud security zone group."""

    def __init__(self, hap: HomematicipHAP, device, post: str = "SecurityZone") -> None:
        """Initialize security zone group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post)

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SAFETY

    @property
    def available(self) -> bool:
        """Security-Group available."""
        # A security-group must be available, and should not be affected by
        # the individual availability of group members.
        return True

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the security zone group."""
        state_attr = super().device_state_attributes

        for attr, attr_key in GROUP_ATTRIBUTES.items():
            attr_value = getattr(self._device, attr, None)
            if attr_value:
                state_attr[attr_key] = attr_value

        window_state = getattr(self._device, "windowState", None)
        if window_state and window_state != WindowState.CLOSED:
            state_attr[ATTR_WINDOW_STATE] = str(window_state)

        return state_attr

    @property
    def is_on(self) -> bool:
        """Return true if security issue detected."""
        if (
            self._device.motionDetected
            or self._device.presenceDetected
            or self._device.unreach
            or self._device.sabotage
        ):
            return True

        if (
            self._device.windowState is not None
            and self._device.windowState != WindowState.CLOSED
        ):
            return True
        return False


class HomematicipSecuritySensorGroup(
    HomematicipSecurityZoneSensorGroup, BinarySensorDevice
):
    """Representation of a HomematicIP security group."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize security group."""
        super().__init__(hap, device, "Sensors")

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the security group."""
        state_attr = super().device_state_attributes

        smoke_detector_at = getattr(self._device, "smokeDetectorAlarmType", None)
        if smoke_detector_at and smoke_detector_at != SmokeDetectorAlarmType.IDLE_OFF:
            state_attr[ATTR_SMOKE_DETECTOR_ALARM] = str(smoke_detector_at)

        return state_attr

    @property
    def is_on(self) -> bool:
        """Return true if safety issue detected."""
        parent_is_on = super().is_on
        if parent_is_on:
            return True

        if (
            self._device.powerMainsFailure
            or self._device.moistureDetected
            or self._device.waterlevelDetected
            or self._device.lowBat
            or self._device.dutyCycle
        ):
            return True

        if (
            self._device.smokeDetectorAlarmType is not None
            and self._device.smokeDetectorAlarmType != SmokeDetectorAlarmType.IDLE_OFF
        ):
            return True

        return False
