"""Support for Dyson Pure Hot+Cool link fan."""
import logging

from libpurecool.const import (
    AutoMode,
    FanPower,
    FanSpeed,
    FanState,
    FocusMode,
    HeatMode,
    HeatState,
    HeatTarget,
)
from libpurecool.dyson_pure_hotcool import DysonPureHotCool
from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
from libpurecool.dyson_pure_state import DysonPureHotCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureHotCoolV2State

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DYSON_DEVICES, DysonEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_FAN = [FAN_FOCUS, FAN_DIFFUSE]
SUPPORT_FAN_PCOOL = [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
SUPPORT_HVAC = [HVAC_MODE_COOL, HVAC_MODE_HEAT]
SUPPORT_HVAC_PCOOL = [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

DYSON_KNOWN_CLIMATE_DEVICES = "dyson_known_climate_devices"

SPEED_MAP = {
    FanSpeed.FAN_SPEED_1.value: FAN_LOW,
    FanSpeed.FAN_SPEED_2.value: FAN_LOW,
    FanSpeed.FAN_SPEED_3.value: FAN_LOW,
    FanSpeed.FAN_SPEED_4.value: FAN_LOW,
    FanSpeed.FAN_SPEED_AUTO.value: FAN_AUTO,
    FanSpeed.FAN_SPEED_5.value: FAN_MEDIUM,
    FanSpeed.FAN_SPEED_6.value: FAN_MEDIUM,
    FanSpeed.FAN_SPEED_7.value: FAN_MEDIUM,
    FanSpeed.FAN_SPEED_8.value: FAN_HIGH,
    FanSpeed.FAN_SPEED_9.value: FAN_HIGH,
    FanSpeed.FAN_SPEED_10.value: FAN_HIGH,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson fan components."""
    if discovery_info is None:
        return

    known_devices = hass.data.setdefault(DYSON_KNOWN_CLIMATE_DEVICES, set())

    # Get Dyson Devices from parent component
    new_entities = []

    for device in hass.data[DYSON_DEVICES]:
        if device.serial not in known_devices:
            if isinstance(device, DysonPureHotCool):
                dyson_entity = DysonPureHotCoolEntity(device)
                new_entities.append(dyson_entity)
                known_devices.add(device.serial)
            elif isinstance(device, DysonPureHotCoolLink):
                dyson_entity = DysonPureHotCoolLinkEntity(device)
                new_entities.append(dyson_entity)
                known_devices.add(device.serial)

    add_entities(new_entities)


class DysonClimateEntity(DysonEntity, ClimateEntity):
    """Representation of a Dyson climate fan."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if (
            self._device.environmental_state
            and self._device.environmental_state.temperature
        ):
            temperature_kelvin = self._device.environmental_state.temperature
            return float(f"{temperature_kelvin - 273:.1f}")
        return None

    @property
    def target_temperature(self):
        """Return the target temperature."""
        heat_target = int(self._device.state.heat_target) / 10
        return int(heat_target - 273)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        # Humidity equaling to 0 means invalid value so we don't check for None here
        # https://github.com/home-assistant/core/pull/45172#discussion_r559069756
        if (
            self._device.environmental_state
            and self._device.environmental_state.humidity
        ):
            return self._device.environmental_state.humidity
        return None

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 37

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            _LOGGER.error("Missing target temperature %s", kwargs)
            return
        target_temp = int(target_temp)
        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)
        # Limit the target temperature into acceptable range.
        target_temp = min(self.max_temp, target_temp)
        target_temp = max(self.min_temp, target_temp)
        self.set_heat_target(HeatTarget.celsius(target_temp))

    def set_heat_target(self, heat_target):
        """Set heating target temperature."""


class DysonPureHotCoolLinkEntity(DysonClimateEntity):
    """Representation of a Dyson climate fan."""

    def __init__(self, device):
        """Initialize the fan."""
        super().__init__(device, DysonPureHotCoolState)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._device.state.heat_mode == HeatMode.HEAT_ON.value:
            return HVAC_MODE_HEAT
        return HVAC_MODE_COOL

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._device.state.heat_mode == HeatMode.HEAT_ON.value:
            if self._device.state.heat_state == HeatState.HEAT_STATE_ON.value:
                return CURRENT_HVAC_HEAT
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_COOL

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if self._device.state.focus_mode == FocusMode.FOCUS_ON.value:
            return FAN_FOCUS
        return FAN_DIFFUSE

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return SUPPORT_FAN

    def set_heat_target(self, heat_target):
        """Set heating target temperature."""
        self._device.set_configuration(
            heat_target=heat_target, heat_mode=HeatMode.HEAT_ON
        )

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)
        if fan_mode == FAN_FOCUS:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_ON)
        elif fan_mode == FAN_DIFFUSE:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_OFF)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("Set %s heat mode %s", self.name, hvac_mode)
        if hvac_mode == HVAC_MODE_HEAT:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_ON)
        elif hvac_mode == HVAC_MODE_COOL:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_OFF)


class DysonPureHotCoolEntity(DysonClimateEntity):
    """Representation of a Dyson climate hot+cool fan."""

    def __init__(self, device):
        """Initialize the fan."""
        super().__init__(device, DysonPureHotCoolV2State)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._device.state.fan_power == FanPower.POWER_OFF.value:
            return HVAC_MODE_OFF
        if self._device.state.heat_mode == HeatMode.HEAT_ON.value:
            return HVAC_MODE_HEAT
        return HVAC_MODE_COOL

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC_PCOOL

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._device.state.fan_power == FanPower.POWER_OFF.value:
            return CURRENT_HVAC_OFF
        if self._device.state.heat_mode == HeatMode.HEAT_ON.value:
            if self._device.state.heat_state == HeatState.HEAT_STATE_ON.value:
                return CURRENT_HVAC_HEAT
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_COOL

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if (
            self._device.state.auto_mode != AutoMode.AUTO_ON.value
            and self._device.state.fan_state == FanState.FAN_OFF.value
        ):
            return FAN_OFF

        return SPEED_MAP[self._device.state.speed]

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return SUPPORT_FAN_PCOOL

    def set_heat_target(self, heat_target):
        """Set heating target temperature."""
        self._device.set_heat_target(heat_target)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)
        if fan_mode == FAN_OFF:
            self._device.turn_off()
        elif fan_mode == FAN_LOW:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_4)
        elif fan_mode == FAN_MEDIUM:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_7)
        elif fan_mode == FAN_HIGH:
            self._device.set_fan_speed(FanSpeed.FAN_SPEED_10)
        elif fan_mode == FAN_AUTO:
            self._device.enable_auto_mode()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("Set %s heat mode %s", self.name, hvac_mode)
        if hvac_mode == HVAC_MODE_OFF:
            self._device.turn_off()
        elif self._device.state.fan_power == FanPower.POWER_OFF.value:
            self._device.turn_on()
        if hvac_mode == HVAC_MODE_HEAT:
            self._device.enable_heat_mode()
        elif hvac_mode == HVAC_MODE_COOL:
            self._device.disable_heat_mode()
