"""Support for HomematicIP Cloud binary sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homematicip.base.enums import LockState, SmokeDetectorAlarmType, WindowState
from homematicip.base.functionalChannels import MultiModeInputChannel
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
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP
from .helpers import smoke_detector_channel_data_exists

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


@dataclass(frozen=True)
class HmipBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a HomematicIP binary sensor entity."""

    value_fn: Callable[[Any], bool] = lambda _device: False
    # Preserve unique_id compatibility with legacy per-device class names.
    legacy_class_name: str = ""


# Descriptions for simple binary sensors that can be served by a single
# generic entity class instead of individual subclasses.
SIMPLE_BINARY_SENSOR_DESCRIPTIONS: dict[
    tuple[type, ...], tuple[HmipBinarySensorEntityDescription, ...]
] = {
    (MotionDetectorIndoor, MotionDetectorOutdoor, MotionDetectorPushButton): (
        HmipBinarySensorEntityDescription(
            key="motion_detector",
            name=None,
            device_class=BinarySensorDeviceClass.MOTION,
            value_fn=lambda device: device.motionDetected,
            legacy_class_name="HomematicipMotionDetector",
        ),
    ),
    (PresenceDetectorIndoor,): (
        HmipBinarySensorEntityDescription(
            key="presence_detector",
            name=None,
            device_class=BinarySensorDeviceClass.PRESENCE,
            value_fn=lambda device: device.presenceDetected,
            legacy_class_name="HomematicipPresenceDetector",
        ),
    ),
    (SmokeDetector,): (
        HmipBinarySensorEntityDescription(
            key="smoke_detector",
            name=None,
            device_class=BinarySensorDeviceClass.SMOKE,
            value_fn=lambda device: (
                device.smokeDetectorAlarmType is not None
                and device.smokeDetectorAlarmType
                == SmokeDetectorAlarmType.PRIMARY_ALARM
            ),
            legacy_class_name="HomematicipSmokeDetector",
        ),
    ),
    (WaterSensor,): (
        HmipBinarySensorEntityDescription(
            key="water_detector",
            name=None,
            device_class=BinarySensorDeviceClass.MOISTURE,
            value_fn=lambda device: (
                device.moistureDetected or device.waterlevelDetected
            ),
            legacy_class_name="HomematicipWaterDetector",
        ),
    ),
    (PluggableMainsFailureSurveillance,): (
        HmipBinarySensorEntityDescription(
            key="power_mains",
            name=None,
            device_class=BinarySensorDeviceClass.POWER,
            value_fn=lambda device: not device.powerMainsFailure,
            legacy_class_name="HomematicipPluggableMainsFailureSurveillanceSensor",
        ),
    ),
}

# Weather sensor descriptions — matched separately because multiple
# entity descriptions apply to the same device types.
WEATHER_RAIN_DESCRIPTION = HmipBinarySensorEntityDescription(
    key="rain_sensor",
    translation_key="rain",
    device_class=BinarySensorDeviceClass.MOISTURE,
    value_fn=lambda device: device.raining,
    legacy_class_name="HomematicipRainSensor",
)
RAIN_SENSOR_TYPES = (RainSensor, WeatherSensorPlus, WeatherSensorPro)

BATTERY_DESCRIPTION = HmipBinarySensorEntityDescription(
    key="battery",
    translation_key="battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    value_fn=lambda device: device.lowBat,
    legacy_class_name="HomematicipBatterySensor",
)


def _is_full_flush_lock_controller(device: object) -> bool:
    """Return whether the device is an HmIP-FLC."""
    return getattr(device, "modelType", None) == "HmIP-FLC" and hasattr(
        device, "functionalChannels"
    )


def _get_channel_by_role(
    device: object,
    functional_channel_type: str,
    channel_role: str,
) -> object | None:
    """Return the matching functional channel for the device."""
    for channel in getattr(device, "functionalChannels", []):
        channel_type = getattr(channel, "functionalChannelType", None)
        channel_type_name = getattr(channel_type, "name", channel_type)
        if channel_type_name != functional_channel_type:
            continue
        if getattr(channel, "channelRole", None) != channel_role:
            continue
        return channel
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud binary sensor from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = [HomematicipCloudConnectionSensor(hap)]
    for device in hap.home.devices:
        if isinstance(device, AccelerationSensor):
            entities.append(HomematicipAccelerationSensor(hap, device))
        if isinstance(device, TiltVibrationSensor):
            entities.append(HomematicipTiltVibrationSensor(hap, device))
        if isinstance(device, WiredInput32):
            entities.extend(
                HomematicipMultiContactInterface(
                    hap, device, channel_real_index=channel.index
                )
                for channel in device.functionalChannels
                if isinstance(channel, MultiModeInputChannel)
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

        # Simple binary sensors via entity descriptions
        for device_types, descriptions in SIMPLE_BINARY_SENSOR_DESCRIPTIONS.items():
            if isinstance(device, device_types):
                entities.extend(
                    HomematicipSimpleBinarySensor(hap, device, desc)
                    for desc in descriptions
                )

        # Smoke detector chamber degraded (conditional)
        if isinstance(device, SmokeDetector) and smoke_detector_channel_data_exists(
            device, "chamberDegraded"
        ):
            entities.append(HomematicipSmokeDetectorChamberDegraded(hap, device))

        # Weather rain sensor
        if isinstance(device, RAIN_SENSOR_TYPES):
            entities.append(
                HomematicipSimpleBinarySensor(hap, device, WEATHER_RAIN_DESCRIPTION)
            )

        # Weather sensors that keep their own classes (custom icon / extra attrs)
        if isinstance(device, (WeatherSensor, WeatherSensorPlus, WeatherSensorPro)):
            entities.append(HomematicipStormSensor(hap, device))
            entities.append(HomematicipSunshineSensor(hap, device))

        if _is_full_flush_lock_controller(device):
            entities.append(HomematicipFullFlushLockControllerLocked(hap, device))
            entities.append(HomematicipFullFlushLockControllerGlassBreak(hap, device))

        # Battery sensor for any device with lowBat
        if isinstance(device, Device) and device.lowBat is not None:
            entities.append(
                HomematicipSimpleBinarySensor(hap, device, BATTERY_DESCRIPTION)
            )

    for group in hap.home.groups:
        if isinstance(group, SecurityGroup):
            entities.append(HomematicipSecuritySensorGroup(hap, device=group))
        elif isinstance(group, SecurityZoneGroup):
            entities.append(HomematicipSecurityZoneSensorGroup(hap, device=group))

    async_add_entities(entities)


class HomematicipSimpleBinarySensor(HomematicipGenericEntity, BinarySensorEntity):
    """A binary sensor backed by an entity description."""

    entity_description: HmipBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        hap: HomematicipHAP,
        device: Device,
        description: HmipBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(hap, device)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        """Return a unique ID preserving backward compatibility."""
        return f"{self.entity_description.legacy_class_name}_{self._device.id}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self._device)


# --- Legacy entity classes (not yet converted to entity descriptions) ---


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
        channel_real_index=None,
    ) -> None:
        """Initialize the multi contact entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            is_multi_channel=is_multi_channel,
            channel_real_index=channel_real_index,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the contact interface is on/open."""
        channel = self.get_channel_or_raise()
        if channel.windowState is None:
            return None
        return channel.windowState != WindowState.CLOSED


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


class HomematicipSmokeDetectorChamberDegraded(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP smoke detector chamber health."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize smoke detector chamber health sensor."""
        super().__init__(hap, device, post="Chamber Degraded")

    @property
    def is_on(self) -> bool:
        """Return true if smoke chamber is degraded."""
        return self._device.chamberDegraded


class HomematicipFullFlushLockControllerLocked(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP full flush lock controller lock state."""

    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the full flush lock controller lock sensor."""
        super().__init__(hap, device, post="Locked")

    @property
    def is_on(self) -> bool:
        """Return true if the controlled lock is locked."""
        channel = _get_channel_by_role(
            self._device,
            "MULTI_MODE_LOCK_INPUT_CHANNEL",
            "DOOR_LOCK_SENSOR",
        )
        if channel is None:
            return False
        lock_state = getattr(channel, "lockState", None)
        return getattr(lock_state, "name", lock_state) == LockState.LOCKED.name


class HomematicipFullFlushLockControllerGlassBreak(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP full flush lock controller glass state."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the full flush lock controller glass break sensor."""
        super().__init__(hap, device, post="Glass break")

    @property
    def is_on(self) -> bool:
        """Return true if glass break has been detected."""
        channel = _get_channel_by_role(
            self._device,
            "MULTI_MODE_LOCK_INPUT_CHANNEL",
            "DOOR_LOCK_SENSOR",
        )
        if channel is None:
            return False
        return bool(getattr(channel, "glassBroken", False))


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
