"""Support for HomematicIP Cloud binary sensor."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homematicip.base.enums import (
    BinaryBehaviorType,
    LockState,
    SmokeDetectorAlarmType,
    WindowState,
)
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


def _always_exists(_device: Device) -> bool:
    """Default exists_fn: every matched device gets the entity."""
    return True


@dataclass(frozen=True, kw_only=True)
class HmipBinarySensorDescription[_DeviceT: Device](BinarySensorEntityDescription):
    """Describe a simple HomematicIP binary sensor."""

    value_fn: Callable[[_DeviceT], bool]
    exists_fn: Callable[[_DeviceT], bool] = _always_exists
    # Required: contributes to unique_id via {device.id}_{channel}_{key}. An
    # implicit default would silently lean on get_channel_index()'s fallback
    # and create a migration footgun.
    channel: int


MOTION_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[
        MotionDetectorIndoor | MotionDetectorOutdoor | MotionDetectorPushButton
    ],
    ...,
] = (
    HmipBinarySensorDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda device: device.motionDetected,
        channel=1,
    ),
)

PRESENCE_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[PresenceDetectorIndoor],
    ...,
] = (
    HmipBinarySensorDescription(
        key="presence",
        device_class=BinarySensorDeviceClass.PRESENCE,
        value_fn=lambda device: device.presenceDetected,
        channel=1,
    ),
)

SMOKE_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[SmokeDetector],
    ...,
] = (
    HmipBinarySensorDescription(
        key="smoke",
        device_class=BinarySensorDeviceClass.SMOKE,
        value_fn=lambda device: (
            device.smokeDetectorAlarmType == SmokeDetectorAlarmType.PRIMARY_ALARM
        ),
        channel=1,
    ),
    HmipBinarySensorDescription(
        key="chamber_degraded",
        translation_key="chamber_degraded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.chamberDegraded,
        exists_fn=lambda device: smoke_detector_channel_data_exists(
            device, "chamberDegraded"
        ),
        channel=1,
    ),
)

WATER_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[WaterSensor],
    ...,
] = (
    HmipBinarySensorDescription(
        key="water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: device.moistureDetected or device.waterlevelDetected,
        channel=1,
    ),
)

RAIN_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[RainSensor | WeatherSensorPlus | WeatherSensorPro],
    ...,
] = (
    HmipBinarySensorDescription(
        key="rain",
        translation_key="raining",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: device.raining,
        channel=1,
    ),
)

MAINS_FAILURE_SENSOR_DESCRIPTIONS: tuple[
    HmipBinarySensorDescription[PluggableMainsFailureSurveillance],
    ...,
] = (
    HmipBinarySensorDescription(
        key="mains_failure",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda device: not device.powerMainsFailure,
        channel=1,
    ),
)

BATTERY_SENSOR_DESCRIPTION = HmipBinarySensorDescription[Device](
    key="battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    value_fn=lambda device: bool(device.lowBat),
    channel=0,
)

SIMPLE_BINARY_SENSOR_DESCRIPTIONS: dict[
    tuple[type, ...], tuple[HmipBinarySensorDescription[Any], ...]
] = {
    (
        MotionDetectorIndoor,
        MotionDetectorOutdoor,
        MotionDetectorPushButton,
    ): MOTION_SENSOR_DESCRIPTIONS,
    (PresenceDetectorIndoor,): PRESENCE_SENSOR_DESCRIPTIONS,
    (SmokeDetector,): SMOKE_SENSOR_DESCRIPTIONS,
    (WaterSensor,): WATER_SENSOR_DESCRIPTIONS,
    (RainSensor, WeatherSensorPlus, WeatherSensorPro): RAIN_SENSOR_DESCRIPTIONS,
    (PluggableMainsFailureSurveillance,): MAINS_FAILURE_SENSOR_DESCRIPTIONS,
}


def _create_simple_binary_sensors(
    hap: HomematicipHAP,
    device: Device,
) -> list[HomematicipSimpleBinarySensor[Any]]:
    """Create all simple described binary sensors for a device."""
    entities: list[HomematicipSimpleBinarySensor[Any]] = []

    for device_types, descriptions in SIMPLE_BINARY_SENSOR_DESCRIPTIONS.items():
        if not isinstance(device, device_types):
            continue
        entities.extend(
            HomematicipSimpleBinarySensor(hap, device, description)
            for description in descriptions
            if description.exists_fn(device)
        )
        # Each device class matches at most one group key (enforced by
        # test_simple_binary_sensor_descriptions_no_overlap), so further
        # iteration cannot add entities.
        break

    if device.lowBat is not None:
        entities.append(
            HomematicipSimpleBinarySensor(hap, device, BATTERY_SENSOR_DESCRIPTION)
        )

    return entities


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
        if isinstance(device, Device):
            entities.extend(_create_simple_binary_sensors(hap, device))

        if _is_full_flush_lock_controller(device):
            entities.append(HomematicipFullFlushLockControllerLocked(hap, device))
            entities.append(HomematicipFullFlushLockControllerGlassBreak(hap, device))
        if isinstance(device, (WeatherSensor, WeatherSensorPlus, WeatherSensorPro)):
            entities.append(HomematicipStormSensor(hap, device))
            entities.append(HomematicipSunshineSensor(hap, device))

    for group in hap.home.groups:
        if isinstance(group, SecurityGroup):
            entities.append(HomematicipSecuritySensorGroup(hap, device=group))
        elif isinstance(group, SecurityZoneGroup):
            entities.append(HomematicipSecurityZoneSensorGroup(hap, device=group))

    async_add_entities(entities)


class HomematicipSimpleBinarySensor[_DeviceT: Device](
    HomematicipGenericEntity, BinarySensorEntity
):
    """A simple HomematicIP binary sensor backed by an entity description."""

    entity_description: HmipBinarySensorDescription[_DeviceT]

    def __init__(
        self,
        hap: HomematicipHAP,
        device: _DeviceT,
        description: HmipBinarySensorDescription[_DeviceT],
    ) -> None:
        """Initialize the described binary sensor."""
        super().__init__(
            hap,
            device,
            channel=description.channel,
            feature_id=description.key,
            use_description_name=True,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on."""
        return self.entity_description.value_fn(self._device)


class HomematicipCloudConnectionSensor(HomematicipGenericEntity, BinarySensorEntity):
    """Representation of the HomematicIP cloud connection sensor."""

    _attr_translation_key = "cloud_connection"

    def __init__(self, hap: HomematicipHAP) -> None:
        """Initialize the cloud connection sensor."""
        super().__init__(hap, hap.home, feature_id="cloud_connection")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        # Merges into the existing HAP device registered in __init__.py.
        # Name must match __init__.py logic for has_entity_name to work.
        label = self._home.label or ""
        return DeviceInfo(
            identifiers={
                # Serial numbers of Homematic IP device
                (DOMAIN, self._home.id)
            },
            name=label,
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

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the acceleration sensor."""
        super().__init__(hap, device, feature_id="acceleration")


class HomematicipTiltVibrationSensor(HomematicipBaseActionSensor):
    """Representation of the HomematicIP tilt vibration sensor."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the tilt vibration sensor."""
        super().__init__(hap, device, feature_id="tilt_vibration")


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
        feature_id: str = "contact",
    ) -> None:
        """Initialize the multi contact entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            is_multi_channel=is_multi_channel,
            channel_real_index=channel_real_index,
            feature_id=feature_id,
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
        super().__init__(hap, device, is_multi_channel=False, feature_id="contact")


class HomematicipShutterContact(HomematicipMultiContactInterface, BinarySensorEntity):
    """Representation of the HomematicIP shutter contact."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self, hap: HomematicipHAP, device, has_additional_state: bool = False
    ) -> None:
        """Initialize the shutter contact."""
        super().__init__(
            hap, device, is_multi_channel=False, feature_id="shutter_contact"
        )
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


class HomematicipFullFlushLockControllerLocked(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP full flush lock controller lock state."""

    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the full flush lock controller lock sensor."""
        super().__init__(hap, device, post="Locked", feature_id="lock_locked")

    @property
    def is_on(self) -> bool:
        """Return true if the controlled lock is unlocked.

        Per HA's BinarySensorDeviceClass.LOCK contract, ON means
        unlocked / open and OFF means locked / closed.

        The mapping from the firmware-reported ``lockState`` depends on
        the channel's ``binaryBehaviorType``. With the default
        ``NORMALLY_OPEN`` wiring, the input goes ACTIVE (and lockState
        flips to ``LOCKED``) when the contact closes — i.e. when a
        magnetic door contact registers the door as closed. With
        ``NORMALLY_CLOSE`` the same physical event puts the input into
        the IDLE state (lockState ``UNLOCKED``). To present the same
        HA semantics regardless of which way the user wired the
        contact, ``lockState`` is interpreted relative to the
        configured behavior.
        """
        channel = _get_channel_by_role(
            self._device,
            "MULTI_MODE_LOCK_INPUT_CHANNEL",
            "DOOR_LOCK_SENSOR",
        )
        if channel is None:
            return False
        lock_state = getattr(channel, "lockState", None)
        is_locked_state = (
            getattr(lock_state, "name", lock_state) == LockState.LOCKED.name
        )
        binary_behavior = getattr(channel, "binaryBehaviorType", None)
        normally_close = (
            getattr(binary_behavior, "name", binary_behavior)
            == BinaryBehaviorType.NORMALLY_CLOSE.name
        )
        return is_locked_state if normally_close else not is_locked_state


class HomematicipFullFlushLockControllerGlassBreak(
    HomematicipGenericEntity, BinarySensorEntity
):
    """Representation of the HomematicIP full flush lock controller glass state."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the full flush lock controller glass break sensor."""
        super().__init__(hap, device, post="Glass break", feature_id="glass_break")

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
        super().__init__(hap, device, "Storm", feature_id="storm")

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
        super().__init__(hap, device, post="Sunshine", feature_id="sunshine")

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

    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        post: str = "SecurityZone",
        feature_id: str = "security_zone",
    ) -> None:
        """Initialize security zone group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post=post, feature_id=feature_id)

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
        super().__init__(hap, device, post="Sensors", feature_id="security")

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
