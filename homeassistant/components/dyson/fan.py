"""Support for Dyson Pure Cool link fan."""
import logging
from typing import Optional

from libpurecool.const import FanMode, FanSpeed, NightMode, Oscillation
from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink
from libpurecool.dyson_pure_state import DysonPureCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureCoolV2State
import voluptuous as vol

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers import config_validation as cv, entity_platform

from . import DYSON_DEVICES, DysonEntity

_LOGGER = logging.getLogger(__name__)

ATTR_NIGHT_MODE = "night_mode"
ATTR_AUTO_MODE = "auto_mode"
ATTR_ANGLE_LOW = "angle_low"
ATTR_ANGLE_HIGH = "angle_high"
ATTR_FLOW_DIRECTION_FRONT = "flow_direction_front"
ATTR_TIMER = "timer"
ATTR_HEPA_FILTER = "hepa_filter"
ATTR_CARBON_FILTER = "carbon_filter"
ATTR_DYSON_SPEED = "dyson_speed"
ATTR_DYSON_SPEED_LIST = "dyson_speed_list"

DYSON_DOMAIN = "dyson"
DYSON_FAN_DEVICES = "dyson_fan_devices"

SERVICE_SET_NIGHT_MODE = "set_night_mode"
SERVICE_SET_AUTO_MODE = "set_auto_mode"
SERVICE_SET_ANGLE = "set_angle"
SERVICE_SET_FLOW_DIRECTION_FRONT = "set_flow_direction_front"
SERVICE_SET_TIMER = "set_timer"
SERVICE_SET_DYSON_SPEED = "set_speed"

SET_NIGHT_MODE_SCHEMA = {
    vol.Required(ATTR_NIGHT_MODE): cv.boolean,
}

SET_AUTO_MODE_SCHEMA = {
    vol.Required(ATTR_AUTO_MODE): cv.boolean,
}

SET_ANGLE_SCHEMA = {
    vol.Required(ATTR_ANGLE_LOW): cv.positive_int,
    vol.Required(ATTR_ANGLE_HIGH): cv.positive_int,
}

SET_FLOW_DIRECTION_FRONT_SCHEMA = {
    vol.Required(ATTR_FLOW_DIRECTION_FRONT): cv.boolean,
}

SET_TIMER_SCHEMA = {
    vol.Required(ATTR_TIMER): cv.positive_int,
}

SET_DYSON_SPEED_SCHEMA = {
    vol.Required(ATTR_DYSON_SPEED): cv.positive_int,
}


SPEED_LIST_HA = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SPEED_LIST_DYSON = [
    int(FanSpeed.FAN_SPEED_1.value),
    int(FanSpeed.FAN_SPEED_2.value),
    int(FanSpeed.FAN_SPEED_3.value),
    int(FanSpeed.FAN_SPEED_4.value),
    int(FanSpeed.FAN_SPEED_5.value),
    int(FanSpeed.FAN_SPEED_6.value),
    int(FanSpeed.FAN_SPEED_7.value),
    int(FanSpeed.FAN_SPEED_8.value),
    int(FanSpeed.FAN_SPEED_9.value),
    int(FanSpeed.FAN_SPEED_10.value),
]

SPEED_DYSON_TO_HA = {
    FanSpeed.FAN_SPEED_1.value: SPEED_LOW,
    FanSpeed.FAN_SPEED_2.value: SPEED_LOW,
    FanSpeed.FAN_SPEED_3.value: SPEED_LOW,
    FanSpeed.FAN_SPEED_4.value: SPEED_LOW,
    FanSpeed.FAN_SPEED_AUTO.value: SPEED_MEDIUM,
    FanSpeed.FAN_SPEED_5.value: SPEED_MEDIUM,
    FanSpeed.FAN_SPEED_6.value: SPEED_MEDIUM,
    FanSpeed.FAN_SPEED_7.value: SPEED_MEDIUM,
    FanSpeed.FAN_SPEED_8.value: SPEED_HIGH,
    FanSpeed.FAN_SPEED_9.value: SPEED_HIGH,
    FanSpeed.FAN_SPEED_10.value: SPEED_HIGH,
}

SPEED_HA_TO_DYSON = {
    SPEED_LOW: FanSpeed.FAN_SPEED_4,
    SPEED_MEDIUM: FanSpeed.FAN_SPEED_7,
    SPEED_HIGH: FanSpeed.FAN_SPEED_10,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dyson fan components."""

    if discovery_info is None:
        return

    _LOGGER.debug("Creating new Dyson fans")
    if DYSON_FAN_DEVICES not in hass.data:
        hass.data[DYSON_FAN_DEVICES] = []

    # Get Dyson Devices from parent component
    has_purecool_devices = False
    device_serials = [device.serial for device in hass.data[DYSON_FAN_DEVICES]]
    for device in hass.data[DYSON_DEVICES]:
        if device.serial not in device_serials:
            if isinstance(device, DysonPureCool):
                has_purecool_devices = True
                dyson_entity = DysonPureCoolEntity(device)
                hass.data[DYSON_FAN_DEVICES].append(dyson_entity)
            elif isinstance(device, DysonPureCoolLink):
                dyson_entity = DysonPureCoolLinkEntity(device)
                hass.data[DYSON_FAN_DEVICES].append(dyson_entity)

    async_add_entities(hass.data[DYSON_FAN_DEVICES])

    # Register custom services
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SET_NIGHT_MODE, SET_NIGHT_MODE_SCHEMA, "set_night_mode"
    )
    platform.async_register_entity_service(
        SERVICE_SET_AUTO_MODE, SET_AUTO_MODE_SCHEMA, "set_auto_mode"
    )
    platform.async_register_entity_service(
        SERVICE_SET_DYSON_SPEED, SET_DYSON_SPEED_SCHEMA, "service_set_dyson_speed"
    )
    if has_purecool_devices:
        platform.async_register_entity_service(
            SERVICE_SET_ANGLE, SET_ANGLE_SCHEMA, "set_angle"
        )
        platform.async_register_entity_service(
            SERVICE_SET_FLOW_DIRECTION_FRONT,
            SET_FLOW_DIRECTION_FRONT_SCHEMA,
            "set_flow_direction_front",
        )
        platform.async_register_entity_service(
            SERVICE_SET_TIMER, SET_TIMER_SCHEMA, "set_timer"
        )


class DysonFanEntity(DysonEntity, FanEntity):
    """Representation of a Dyson fan."""

    @property
    def speed(self):
        """Return the current speed."""
        return SPEED_DYSON_TO_HA[self._device.state.speed]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SPEED_LIST_HA

    @property
    def dyson_speed(self):
        """Return the current speed."""
        if self._device.state.speed == FanSpeed.FAN_SPEED_AUTO.value:
            return self._device.state.speed
        return int(self._device.state.speed)

    @property
    def dyson_speed_list(self) -> list:
        """Get the list of available dyson speeds."""
        return SPEED_LIST_DYSON

    @property
    def night_mode(self):
        """Return Night mode."""
        return self._device.state.night_mode == "ON"

    @property
    def auto_mode(self):
        """Return auto mode."""
        raise NotImplementedError

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

    @property
    def device_state_attributes(self) -> dict:
        """Return optional state attributes."""
        return {
            ATTR_NIGHT_MODE: self.night_mode,
            ATTR_AUTO_MODE: self.auto_mode,
            ATTR_DYSON_SPEED: self.dyson_speed,
            ATTR_DYSON_SPEED_LIST: self.dyson_speed_list,
        }

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed not in SPEED_LIST_HA:
            raise ValueError(f'"{speed}" is not a valid speed')
        _LOGGER.debug("Set fan speed to: %s", speed)
        self.set_dyson_speed(SPEED_HA_TO_DYSON[speed])

    def set_dyson_speed(self, speed: FanSpeed) -> None:
        """Set the exact speed of the fan."""
        raise NotImplementedError

    def service_set_dyson_speed(self, dyson_speed: str) -> None:
        """Handle the service to set dyson speed."""
        if dyson_speed not in SPEED_LIST_DYSON:
            raise ValueError(f'"{dyson_speed}" is not a valid Dyson speed')
        _LOGGER.debug("Set exact speed to %s", dyson_speed)
        speed = FanSpeed(f"{int(dyson_speed):04d}")
        self.set_dyson_speed(speed)


class DysonPureCoolLinkEntity(DysonFanEntity):
    """Representation of a Dyson fan."""

    def __init__(self, device):
        """Initialize the fan."""
        super().__init__(device, DysonPureCoolState)

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    def turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s with speed %s", self.name, speed)
        if speed is not None:
            self.set_speed(speed)
        else:
            # Speed not set, just turn on
            self._device.set_configuration(fan_mode=FanMode.FAN)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turn off fan %s", self.name)
        self._device.set_configuration(fan_mode=FanMode.OFF)

    def set_dyson_speed(self, speed: FanSpeed) -> None:
        """Set the exact speed of the fan."""
        self._device.set_configuration(fan_mode=FanMode.FAN, fan_speed=speed)

    def oscillate(self, oscillating: bool) -> None:
        """Turn on/off oscillating."""
        _LOGGER.debug("Turn oscillation %s for device %s", oscillating, self.name)

        if oscillating:
            self._device.set_configuration(oscillation=Oscillation.OSCILLATION_ON)
        else:
            self._device.set_configuration(oscillation=Oscillation.OSCILLATION_OFF)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._device.state.oscillation == "ON"

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self._device.state.fan_mode in ["FAN", "AUTO"]

    def set_night_mode(self, night_mode: bool) -> None:
        """Turn fan in night mode."""
        _LOGGER.debug("Set %s night mode %s", self.name, night_mode)
        if night_mode:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_ON)
        else:
            self._device.set_configuration(night_mode=NightMode.NIGHT_MODE_OFF)

    @property
    def auto_mode(self):
        """Return auto mode."""
        return self._device.state.fan_mode == "AUTO"

    def set_auto_mode(self, auto_mode: bool) -> None:
        """Turn fan in auto mode."""
        _LOGGER.debug("Set %s auto mode %s", self.name, auto_mode)
        if auto_mode:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            self._device.set_configuration(fan_mode=FanMode.FAN)


class DysonPureCoolEntity(DysonFanEntity):
    """Representation of a Dyson Purecool (TP04/DP04) fan."""

    def __init__(self, device):
        """Initialize the fan."""
        super().__init__(device, DysonPureCoolV2State)

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    def turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s", self.name)

        if speed is not None:
            self.set_speed(speed)
        else:
            self._device.turn_on()

    def turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turn off fan %s", self.name)
        self._device.turn_off()

    def set_dyson_speed(self, speed: FanSpeed) -> None:
        """Set the exact speed of the purecool fan."""
        self._device.set_fan_speed(speed)

    def oscillate(self, oscillating: bool) -> None:
        """Turn on/off oscillating."""
        _LOGGER.debug("Turn oscillation %s for device %s", oscillating, self.name)

        if oscillating:
            self._device.enable_oscillation()
        else:
            self._device.disable_oscillation()

    def set_night_mode(self, night_mode: bool) -> None:
        """Turn on/off night mode."""
        _LOGGER.debug("Turn night mode %s for device %s", night_mode, self.name)

        if night_mode:
            self._device.enable_night_mode()
        else:
            self._device.disable_night_mode()

    def set_auto_mode(self, auto_mode: bool) -> None:
        """Turn auto mode on/off."""
        _LOGGER.debug("Turn auto mode %s for device %s", auto_mode, self.name)
        if auto_mode:
            self._device.enable_auto_mode()
        else:
            self._device.disable_auto_mode()

    def set_angle(self, angle_low: int, angle_high: int) -> None:
        """Set device angle."""
        _LOGGER.debug(
            "set low %s and high angle %s for device %s",
            angle_low,
            angle_high,
            self.name,
        )
        self._device.enable_oscillation(angle_low, angle_high)

    def set_flow_direction_front(self, flow_direction_front: bool) -> None:
        """Set frontal airflow direction."""
        _LOGGER.debug(
            "Set frontal flow direction to %s for device %s",
            flow_direction_front,
            self.name,
        )

        if flow_direction_front:
            self._device.enable_frontal_direction()
        else:
            self._device.disable_frontal_direction()

    def set_timer(self, timer) -> None:
        """Set timer."""
        _LOGGER.debug("Set timer to %s for device %s", timer, self.name)

        if timer == 0:
            self._device.disable_sleep_timer()
        else:
            self._device.enable_sleep_timer(timer)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._device.state and self._device.state.oscillation == "OION"

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self._device.state.fan_power == "ON"

    @property
    def auto_mode(self):
        """Return Auto mode."""
        return self._device.state.auto_mode == "ON"

    @property
    def angle_low(self):
        """Return angle high."""
        return int(self._device.state.oscillation_angle_low)

    @property
    def angle_high(self):
        """Return angle low."""
        return int(self._device.state.oscillation_angle_high)

    @property
    def flow_direction_front(self):
        """Return frontal flow direction."""
        return self._device.state.front_direction == "ON"

    @property
    def timer(self):
        """Return timer."""
        return self._device.state.sleep_timer

    @property
    def hepa_filter(self):
        """Return the HEPA filter state."""
        return int(self._device.state.hepa_filter_state)

    @property
    def carbon_filter(self):
        """Return the carbon filter state."""
        if self._device.state.carbon_filter_state == "INV":
            return self._device.state.carbon_filter_state
        return int(self._device.state.carbon_filter_state)

    @property
    def device_state_attributes(self) -> dict:
        """Return optional state attributes."""
        return {
            **super().device_state_attributes,
            ATTR_ANGLE_LOW: self.angle_low,
            ATTR_ANGLE_HIGH: self.angle_high,
            ATTR_FLOW_DIRECTION_FRONT: self.flow_direction_front,
            ATTR_TIMER: self.timer,
            ATTR_HEPA_FILTER: self.hepa_filter,
            ATTR_CARBON_FILTER: self.carbon_filter,
        }
