"""Support for Dyson Pure Cool link fan."""
import logging

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
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv

from . import DYSON_DEVICES

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

DYSON_SET_NIGHT_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_NIGHT_MODE): cv.boolean,
    }
)

SET_AUTO_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_AUTO_MODE): cv.boolean,
    }
)

SET_ANGLE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ANGLE_LOW): cv.positive_int,
        vol.Required(ATTR_ANGLE_HIGH): cv.positive_int,
    }
)

SET_FLOW_DIRECTION_FRONT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_FLOW_DIRECTION_FRONT): cv.boolean,
    }
)

SET_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TIMER): cv.positive_int,
    }
)

SET_DYSON_SPEED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DYSON_SPEED): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
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
                dyson_entity = DysonPureCoolDevice(device)
                hass.data[DYSON_FAN_DEVICES].append(dyson_entity)
            elif isinstance(device, DysonPureCoolLink):
                dyson_entity = DysonPureCoolLinkDevice(hass, device)
                hass.data[DYSON_FAN_DEVICES].append(dyson_entity)

    add_entities(hass.data[DYSON_FAN_DEVICES])

    def service_handle(service):
        """Handle the Dyson services."""
        entity_id = service.data[ATTR_ENTITY_ID]
        fan_device = next(
            (fan for fan in hass.data[DYSON_FAN_DEVICES] if fan.entity_id == entity_id),
            None,
        )
        if fan_device is None:
            _LOGGER.warning("Unable to find Dyson fan device %s", str(entity_id))
            return

        if service.service == SERVICE_SET_NIGHT_MODE:
            fan_device.set_night_mode(service.data[ATTR_NIGHT_MODE])

        if service.service == SERVICE_SET_AUTO_MODE:
            fan_device.set_auto_mode(service.data[ATTR_AUTO_MODE])

        if service.service == SERVICE_SET_ANGLE:
            fan_device.set_angle(
                service.data[ATTR_ANGLE_LOW], service.data[ATTR_ANGLE_HIGH]
            )

        if service.service == SERVICE_SET_FLOW_DIRECTION_FRONT:
            fan_device.set_flow_direction_front(service.data[ATTR_FLOW_DIRECTION_FRONT])

        if service.service == SERVICE_SET_TIMER:
            fan_device.set_timer(service.data[ATTR_TIMER])

        if service.service == SERVICE_SET_DYSON_SPEED:
            fan_device.set_dyson_speed(service.data[ATTR_DYSON_SPEED])

    # Register dyson service(s)
    hass.services.register(
        DYSON_DOMAIN,
        SERVICE_SET_NIGHT_MODE,
        service_handle,
        schema=DYSON_SET_NIGHT_MODE_SCHEMA,
    )

    hass.services.register(
        DYSON_DOMAIN, SERVICE_SET_AUTO_MODE, service_handle, schema=SET_AUTO_MODE_SCHEMA
    )
    if has_purecool_devices:
        hass.services.register(
            DYSON_DOMAIN, SERVICE_SET_ANGLE, service_handle, schema=SET_ANGLE_SCHEMA
        )

        hass.services.register(
            DYSON_DOMAIN,
            SERVICE_SET_FLOW_DIRECTION_FRONT,
            service_handle,
            schema=SET_FLOW_DIRECTION_FRONT_SCHEMA,
        )

        hass.services.register(
            DYSON_DOMAIN, SERVICE_SET_TIMER, service_handle, schema=SET_TIMER_SCHEMA
        )

        hass.services.register(
            DYSON_DOMAIN,
            SERVICE_SET_DYSON_SPEED,
            service_handle,
            schema=SET_DYSON_SPEED_SCHEMA,
        )


class DysonPureCoolLinkDevice(FanEntity):
    """Representation of a Dyson fan."""

    def __init__(self, hass, device):
        """Initialize the fan."""
        _LOGGER.debug("Creating device %s", device.name)
        self.hass = hass
        self._device = device

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(self._device.add_message_listener, self.on_message)

    def on_message(self, message):
        """Call when new messages received from the fan."""

        if isinstance(message, DysonPureCoolState):
            _LOGGER.debug("Message received for fan device %s: %s", self.name, message)
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._device.name

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan. Never called ??."""
        _LOGGER.debug("Set fan speed to: %s", speed)

        if speed == FanSpeed.FAN_SPEED_AUTO.value:
            self._device.set_configuration(fan_mode=FanMode.AUTO)
        else:
            fan_speed = FanSpeed(f"{int(speed):04d}")
            self._device.set_configuration(fan_mode=FanMode.FAN, fan_speed=fan_speed)

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s with speed %s", self.name, speed)
        if speed:
            if speed == FanSpeed.FAN_SPEED_AUTO.value:
                self._device.set_configuration(fan_mode=FanMode.AUTO)
            else:
                fan_speed = FanSpeed(f"{int(speed):04d}")
                self._device.set_configuration(
                    fan_mode=FanMode.FAN, fan_speed=fan_speed
                )
        else:
            # Speed not set, just turn on
            self._device.set_configuration(fan_mode=FanMode.FAN)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turn off fan %s", self.name)
        self._device.set_configuration(fan_mode=FanMode.OFF)

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
        return self._device.state and self._device.state.oscillation == "ON"

    @property
    def is_on(self):
        """Return true if the entity is on."""
        if self._device.state:
            return self._device.state.fan_mode == "FAN"
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self._device.state:
            if self._device.state.speed == FanSpeed.FAN_SPEED_AUTO.value:
                return self._device.state.speed
            return int(self._device.state.speed)
        return None

    @property
    def current_direction(self):
        """Return direction of the fan [forward, reverse]."""
        return None

    @property
    def night_mode(self):
        """Return Night mode."""
        return self._device.state.night_mode == "ON"

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

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        supported_speeds = [
            FanSpeed.FAN_SPEED_AUTO.value,
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

        return supported_speeds

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

    @property
    def device_state_attributes(self) -> dict:
        """Return optional state attributes."""
        return {ATTR_NIGHT_MODE: self.night_mode, ATTR_AUTO_MODE: self.auto_mode}


class DysonPureCoolDevice(FanEntity):
    """Representation of a Dyson Purecool (TP04/DP04) fan."""

    def __init__(self, device):
        """Initialize the fan."""
        self._device = device

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_executor_job(
            self._device.add_message_listener, self.on_message
        )

    def on_message(self, message):
        """Call when new messages received from the fan."""
        if isinstance(message, DysonPureCoolV2State):
            _LOGGER.debug("Message received for fan device %s: %s", self.name, message)
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._device.name

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turn on fan %s", self.name)

        if speed is not None:
            self.set_speed(speed)
        else:
            self._device.turn_on()

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed == SPEED_LOW:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_4)
        elif speed == SPEED_MEDIUM:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_7)
        elif speed == SPEED_HIGH:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_10)

    def turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turn off fan %s", self.name)
        self._device.turn_off()

    def set_dyson_speed(self, speed: str = None) -> None:
        """Set the exact speed of the purecool fan."""
        _LOGGER.debug("Set exact speed for fan %s", self.name)

        fan_speed = FanSpeed(f"{int(speed):04d}")
        self._device.set_fan_speed(fan_speed)

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
        if self._device.state:
            return self._device.state.fan_power == "ON"

    @property
    def speed(self):
        """Return the current speed."""
        speed_map = {
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

        return speed_map[self._device.state.speed]

    @property
    def dyson_speed(self):
        """Return the current speed."""
        if self._device.state:
            if self._device.state.speed == FanSpeed.FAN_SPEED_AUTO.value:
                return self._device.state.speed
            return int(self._device.state.speed)

    @property
    def night_mode(self):
        """Return Night mode."""
        return self._device.state.night_mode == "ON"

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
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def dyson_speed_list(self) -> list:
        """Get the list of available dyson speeds."""
        return [
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

    @property
    def device_serial(self):
        """Return fan's serial number."""
        return self._device.serial

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
            ATTR_ANGLE_LOW: self.angle_low,
            ATTR_ANGLE_HIGH: self.angle_high,
            ATTR_FLOW_DIRECTION_FRONT: self.flow_direction_front,
            ATTR_TIMER: self.timer,
            ATTR_HEPA_FILTER: self.hepa_filter,
            ATTR_CARBON_FILTER: self.carbon_filter,
            ATTR_DYSON_SPEED: self.dyson_speed,
            ATTR_DYSON_SPEED_LIST: self.dyson_speed_list,
        }
