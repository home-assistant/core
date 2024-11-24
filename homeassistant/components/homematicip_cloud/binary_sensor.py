"""Support for HomematicIP Cloud binary sensor."""

from __future__ import annotations

from typing import Any

from homematicip.base.enums import SmokeDetectorAlarmType, WindowState
from homematicip.device import (
    AccelerationSensor,
    ContactInterface,
    Device,
    FullFlushContactInterface,
    FullFlushContactInterface6,
    MotionDetectorIndoor,
    MotionDetectorOutdoor,
    MotionDetectorPushButton,
    PluggableMainsFailureSurveillance,
    PresenceDetectorIndoor,
    RainSensor,
    RotaryHandleSensor,
    ShutterContact,
    ShutterContactMagnetic,
    SmokeDetector,
    TiltVibrationSensor,
    WaterSensor,
    WeatherSensor,
    WeatherSensorPlus,
    WeatherSensorPro,
    WiredInput32,
)
from homematicip.group import SecurityGroup, SecurityZoneGroup

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicipHAP

ATTR_ACCELERATION_SENSOR_MODE = "acceleration_sensor_mode"
ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION = "acceleration_sensor_neutral_position"
ATTR_ACCELERATION_SENSOR_SENSITIVITY = "acceleration_sensor_sensitivity"
ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE = "acceleration_sensor_trigger_angle"
ATTR_INTRUSION_ALARM = "intrusion_alarm"
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
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud binary sensor from a config entry."""
    hap = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = [HomematicipCloudConnectionSensor(hap)]
    for device in hap.home.devices:
        if isinstance(device, AccelerationSensor):
            entities.append(HomematicipAccelerationSensor(hap, device))
        if isinstance(device, TiltVibrationSensor):
            entities.append(HomematicipTiltVibrationSensor(hap, device))
        if isinstance(device, WiredInput32):
            entities.extend(
                HomematicipMultiContactInterface(hap, device, channel=channel)
                for channel in range(1, 33)
            )
        elif isinstance(device, FullFlushContactInterface6):
            entities.extend(
                HomematicipMultiContactInterface(hap, device, channel=channel)
                for channel in range(1, 7)
            )
        elif isinstance(device, (ContactInterface, FullFlushContactInterface)):
            entities.append(HomematicipContactInterface(hap, device))
        if isinstance(
            device,
            (ShutterContact, ShutterContactMagnetic),
        ):
            entities.append(HomematicipShutterContact(hap, device))
        if isinstance(device, RotaryHandleSensor):
            entities.append(HomematicipShutterContact(hap, device, True))
        if isinstance(
            device,
            (
                MotionDetectorIndoor,
                MotionDetectorOutdoor,
                MotionDetectorPushButton,
            ),
        ):
            entities.append(HomematicipMotionDetector(hap, device))
        if isinstance(device, PluggableMainsFailureSurveillance):
            entities.append(
                HomematicipPluggableMainsFailureSurveillanceSensor(hap, device)
            )
        if isinstance(device, PresenceDetectorIndoor):
            entities.append(HomematicipPresenceDetector(hap, device))
        if isinstance(device, SmokeDetector):
            entities.append(HomematicipSmokeDetector(hap, device))
        if isinstance(device, WaterSensor):
            entities.append(HomematicipWaterDetector(hap, device))
        if isinstance(device, (RainSensor, WeatherSensorPlus, WeatherSensorPro)):
            entities.append(HomematicipRainSensor(hap, device))
        if isinstance(device, (WeatherSensor, WeatherSensorPlus, WeatherSensorPro)):
            entities.append(HomematicipStormSensor(hap, device))
            entities.append(HomematicipSunshineSensor(hap, device))
        if isinstance(device, Device) and device.lowBat is not None:
            entities.append(HomematicipBatterySensor(hap, device))

    for group in hap.home.groups:
        if isinstance(group, SecurityGroup):
            entities.append(HomematicipSecuritySensorGroup(hap, device=group))
        elif isinstance(group, SecurityZoneGroup):
            entities.append(HomematicipSecurityZoneSensorGroup(hap, device=group))

    async_add_entities(entities)


class HomematicipCloudConnectionSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP cloud connection sensor."""

    def __init__(self, hap: HomematicipHAP) -> None:
        """Initialize the cloud connection sensor."""
        super().__init__(hap, hap.home)

    @property
    def name(self) -> str:
        """Return the name cloud connection entity."""

        name = "Cloud Connection"
        # Add a prefix to the name if the homematic ip home has a name.
        return name if not self._home.name else f"{self._home.name} {name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        # Adds a sensor to the existing HAP device
        return DeviceInfo(
            identifiers={
                # Serial numbers of Homematic IP device
                (DOMAIN, self._home.id)
            }
        )

    @property
    def icon(self) -> str:
        """Return the icon of the access point entity."""
        return (
            "mdi:access-point-network"
            if self._home.connected
            else "mdi:access-point-network-off"
        )

    @property
    def is_on(self) -> bool:
        """Return true if hap is connected to cloud."""
        return self._home.connected

    @property
    def available(self) -> bool:
        """Sensor is always available."""
        return True


class HomematicipBaseActionSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP base action sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOVING

    @property
    def is_on(self) -> bool:
        """Return true if acceleration is detected."""
        return self._device.accelerationSensorTriggered

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the acceleration sensor."""
        state_attr = super().extra_state_attributes

        for attr, attr_key in SAM_DEVICE_ATTRIBUTES.items():
            if attr_value := getattr(self._device, attr, None):
                state_attr[attr_key] = attr_value

        return state_attr


class HomematicipAccelerationSensor(HomematicipBaseActionSensor):
    """Representation of the HomematicIP acceleration sensor."""


class HomematicipTiltVibrationSensor(HomematicipBaseActionSensor):
    """Representation of the HomematicIP tilt vibration sensor."""


class HomematicipMultiContactInterface(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP multi room/area contact interface."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        is_multi_channel=True,
    ) -> None:
        """Initialize the multi contact entity."""
        super().__init__(
            hap, device, channel=channel, is_multi_channel=is_multi_channel
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the contact interface is on/open."""
        if self._device.functionalChannels[self._channel].windowState is None:
            return None
        return (
            self._device.functionalChannels[self._channel].windowState
            != WindowState.CLOSED
        )


class HomematicipContactInterface(HomematicipMultiContactInterface, BinarySensorEntity):
    """Representation of the HomematicIP contact interface."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the multi contact entity."""
        super().__init__(hap, device, is_multi_channel=False)


class HomematicipShutterContact(HomematicipMultiContactInterface, BinarySensorEntity):
    """Representation of the HomematicIP shutter contact."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self, hap: HomematicipHAP, device, has_additional_state: bool = False
    ) -> None:
        """Initialize the shutter contact."""
        super().__init__(hap, device, is_multi_channel=False)
        self.has_additional_state = has_additional_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the Shutter Contact."""
        state_attr = super().extra_state_attributes

        if self.has_additional_state:
            window_state = getattr(self._device, "windowState", None)
            if window_state and window_state != WindowState.CLOSED:
                state_attr[ATTR_WINDOW_STATE] = window_state

        return state_attr


class HomematicipMotionDetector(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP motion detector."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self._device.motionDetected


class HomematicipPresenceDetector(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP presence detector."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    @property
    def is_on(self) -> bool:
        """Return true if presence is detected."""
        return self._device.presenceDetected


class HomematicipSmokeDetector(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP smoke detector."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    @property
    def is_on(self) -> bool:
        """Return true if smoke is detected."""
        if self._device.smokeDetectorAlarmType:
            return (
                self._device.smokeDetectorAlarmType
                == SmokeDetectorAlarmType.PRIMARY_ALARM
            )
        return False


class HomematicipWaterDetector(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP water detector."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true, if moisture or waterlevel is detected."""
        return self._device.moistureDetected or self._device.waterlevelDetected


class HomematicipStormSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP storm sensor."""

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


class HomematicipRainSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP rain sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize rain sensor."""
        super().__init__(hap, device, "Raining")

    @property
    def is_on(self) -> bool:
        """Return true, if it is raining."""
        return self._device.raining


class HomematicipSunshineSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP sunshine sensor."""

    _attr_device_class = BinarySensorDeviceClass.LIGHT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize sunshine sensor."""
        super().__init__(hap, device, post="Sunshine")

    @property
    def is_on(self) -> bool:
        """Return true if sun is shining."""
        return self._device.sunshine

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the illuminance sensor."""
        state_attr = super().extra_state_attributes

        today_sunshine_duration = getattr(self._device, "todaySunshineDuration", None)
        if today_sunshine_duration:
            state_attr[ATTR_TODAY_SUNSHINE_DURATION] = today_sunshine_duration

        return state_attr


class HomematicipBatterySensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP low battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize battery sensor."""
        super().__init__(hap, device, post="Battery")

    @property
    def is_on(self) -> bool:
        """Return true if battery is low."""
        return self._device.lowBat


class HomematicipPluggableMainsFailureSurveillanceSensor(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP pluggable mains failure surveillance sensor."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize pluggable mains failure surveillance sensor."""
        super().__init__(hap, device)

    @property
    def is_on(self) -> bool:
        """Return true if power mains fails."""
        return not self._device.powerMainsFailure


class HomematicipSecurityZoneSensorGroup(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP security zone sensor group."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, hap: HomematicipHAP, device, post: str = "SecurityZone") -> None:
        """Initialize security zone group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post=post)

    @property
    def available(self) -> bool:
        """Security-Group available."""
        # A security-group must be available, and should not be affected by
        # the individual availability of group members.
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the security zone group."""
        state_attr = super().extra_state_attributes

        for attr, attr_key in GROUP_ATTRIBUTES.items():
            if attr_value := getattr(self._device, attr, None):
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
    HomematicipSecurityZoneSensorGroup, BinarySensorEntity
):
    """Representation of the HomematicIP security group."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize security group."""
        super().__init__(hap, device, post="Sensors")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the security group."""
        state_attr = super().extra_state_attributes

        smoke_detector_at = getattr(self._device, "smokeDetectorAlarmType", None)
        if smoke_detector_at:
            if smoke_detector_at == SmokeDetectorAlarmType.PRIMARY_ALARM:
                state_attr[ATTR_SMOKE_DETECTOR_ALARM] = str(smoke_detector_at)
            if smoke_detector_at == SmokeDetectorAlarmType.INTRUSION_ALARM:
                state_attr[ATTR_INTRUSION_ALARM] = str(smoke_detector_at)
        return state_attr

    @property
    def is_on(self) -> bool:
        """Return true if safety issue detected."""
        if super().is_on:
            # parent is on
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
