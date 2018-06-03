"""
Support for Dyson Pure Hot+Cool link fan.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.dyson/
"""
import asyncio
import logging

from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.components.climate import (
    ClimateDevice, STATE_HEAT, STATE_COOL, STATE_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, SUPPORT_OPERATION_MODE)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE
from homeassistant.util.temperature import convert as convert_temperature

_LOGGER = logging.getLogger(__name__)

DYSON_FAN_DEVICES = "dyson_fan_devices"
STATE_DIFFUSE = "Diffuse Mode"
STATE_FOCUS = "Focus Mode"

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
                 | SUPPORT_OPERATION_MODE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dyson fan components."""
    from libpurecoollink.dyson_pure_hotcool_link import DysonPureHotCoolLink

    _LOGGER.debug("Creating new Dyson fans")
    if DYSON_FAN_DEVICES not in hass.data:
        hass.data[DYSON_FAN_DEVICES] = []

    # Get Dyson Devices from parent component.
    for device in [
            d for d in hass.data[DYSON_DEVICES]
            if isinstance(d, DysonPureHotCoolLink)
    ]:
        dyson_entity = DysonPureHotCoolLinkDevice(hass, device)
        hass.data[DYSON_FAN_DEVICES].append(dyson_entity)

    add_devices(hass.data[DYSON_FAN_DEVICES])


class DysonPureHotCoolLinkDevice(ClimateDevice):
    """Representation of a Dyson climate fan."""

    def __init__(self, hass, device):
        """Initialize the fan."""
        _LOGGER.debug("Creating device %s", device.name)
        self.hass = hass
        self._device = device
        self.temp_unit = hass.config.units.temperature_unit
        self._current_temp = None
        self._target_temp = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.async_add_job(self._device.add_message_listener,
                                self.on_message)

    def on_message(self, message):
        """Called when new messages received from the climate."""
        from libpurecoollink.dyson_pure_state import DysonPureHotCoolState

        if isinstance(message, DysonPureHotCoolState):
            from libpurecoollink.const import HeatMode
            _LOGGER.debug("Message received for fan device %s : %s", self.name,
                          message)
            self.schedule_update_ha_state()
            if (self._device.state.heat_mode == HeatMode.HEAT_ON
                    and self._target_temp is not None):
                self.set_temperature()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the display name of this climate."""
        return self._device.name

    @property
    def entity_id(self):
        """Return the entity id of this climate."""
        return "climate.{}".format(self._device.name)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.temp_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._device.environmental_state:
            temperature_kelvin = self._device.environmental_state.temperature
            if temperature_kelvin != 0:
                if self.temp_unit == TEMP_CELSIUS:
                    self._current_temp = float("{0:.1f}".format(
                        self.kelvin_to_celsius(temperature_kelvin)))
                else:
                    self._current_temp = float("{0:.1f}".format(
                        self.kelvin_to_fahrenheit(temperature_kelvin)))
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self._target_temp is None:
            heat_target = int(self._device.state.heat_target) / 10
            if self.temp_unit == TEMP_CELSIUS:
                return int(self.kelvin_to_celsius(heat_target))
            return int(self.kelvin_to_fahrenheit(heat_target))
        return self._target_temp

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self._device.environmental_state:
            if self._device.environmental_state.humidity == 0:
                return None
            return self._device.environmental_state.humidity
        return None

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        from libpurecoollink.const import HeatMode, HeatState
        if self._device.state.heat_mode == HeatMode.HEAT_ON:
            if self._device.state.heat_state == HeatState.HEAT_STATE_ON:
                return STATE_HEAT
            return STATE_IDLE
        return STATE_COOL

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [STATE_HEAT, STATE_COOL]

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        from libpurecoollink.const import FocusMode
        if self._device.state.focus_mode == FocusMode.FOCUS_ON:
            return STATE_FOCUS
        return STATE_DIFFUSE

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return [STATE_FOCUS, STATE_DIFFUSE]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is None:
            return
        target_temp = int(kwargs.get(ATTR_TEMPERATURE))
        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)
        # Limit the target temperature into acceptable range.
        target_temp = min(self.max_temp, target_temp)
        target_temp = max(self.min_temp, target_temp)
        self._target_temp = target_temp
        self.schedule_update_ha_state()
        # Dyson only response when it is in heat mode.
        from libpurecoollink.const import HeatMode
        if self._device.state.heat_mode == HeatMode.HEAT_ON:
            from libpurecoollink.const import HeatTarget
            if self.temp_unit == TEMP_CELSIUS:
                self._device.set_configuration(
                    heat_target=HeatTarget.celsius(self._target_temp))
            elif self.temp_unit == TEMP_FAHRENHEIT:
                self._device.set_configuration(
                    heat_target=HeatTarget.fahrenheit(self._target_temp))
            self._target_temp = None

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)
        from libpurecoollink.const import FocusMode
        if fan_mode == STATE_FOCUS:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_ON)
        elif fan_mode == STATE_DIFFUSE:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_OFF)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s heat mode %s", self.name, operation_mode)
        from libpurecoollink.const import HeatMode
        if operation_mode == STATE_HEAT:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_ON)
        elif operation_mode == STATE_COOL:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_OFF)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(1, TEMP_CELSIUS, self.temp_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(37, TEMP_CELSIUS, self.temp_unit)

    @staticmethod
    def kelvin_to_celsius(kelvin):
        """Convert temperature unit kelvin to celsius."""
        return kelvin - 273

    @staticmethod
    def kelvin_to_fahrenheit(kelvin):
        """Convert temperature unit kelvin to fahrenheit."""
        return kelvin * 9 / 5 - 459.67
