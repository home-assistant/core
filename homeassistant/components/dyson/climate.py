"""Support for Dyson Pure Hot+Cool link fan."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from . import DYSON_DEVICES

_LOGGER = logging.getLogger(__name__)

STATE_DIFFUSE = "Diffuse Mode"
STATE_FOCUS = "Focus Mode"
FAN_LIST = [STATE_FOCUS, STATE_DIFFUSE]
OPERATION_LIST = [STATE_HEAT, STATE_COOL]

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
                 | SUPPORT_OPERATION_MODE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dyson fan components."""
    if discovery_info is None:
        return

    from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
    # Get Dyson Devices from parent component.
    add_devices(
        [DysonPureHotCoolLinkDevice(device)
         for device in hass.data[DYSON_DEVICES]
         if isinstance(device, DysonPureHotCoolLink)]
    )


class DysonPureHotCoolLinkDevice(ClimateDevice):
    """Representation of a Dyson climate fan."""

    def __init__(self, device):
        """Initialize the fan."""
        self._device = device
        self._current_temp = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(self._device.add_message_listener,
                                self.on_message)

    def on_message(self, message):
        """Call when new messages received from the climate."""
        from libpurecool.dyson_pure_state import DysonPureHotCoolState

        if isinstance(message, DysonPureHotCoolState):
            _LOGGER.debug("Message received for climate device %s : %s",
                          self.name, message)
            self.schedule_update_ha_state()

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
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._device.environmental_state:
            temperature_kelvin = self._device.environmental_state.temperature
            if temperature_kelvin != 0:
                self._current_temp = float("{0:.1f}".format(
                    temperature_kelvin - 273))
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the target temperature."""
        heat_target = int(self._device.state.heat_target) / 10
        return int(heat_target - 273)

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
        from libpurecool.const import HeatMode, HeatState
        if self._device.state.heat_mode == HeatMode.HEAT_ON.value:
            if self._device.state.heat_state == HeatState.HEAT_STATE_ON.value:
                return STATE_HEAT
            return STATE_IDLE
        return STATE_COOL

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        from libpurecool.const import FocusMode
        if self._device.state.focus_mode == FocusMode.FOCUS_ON.value:
            return STATE_FOCUS
        return STATE_DIFFUSE

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return FAN_LIST

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return
        target_temp = int(target_temp)
        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)
        # Limit the target temperature into acceptable range.
        target_temp = min(self.max_temp, target_temp)
        target_temp = max(self.min_temp, target_temp)
        from libpurecool.const import HeatTarget, HeatMode
        self._device.set_configuration(
            heat_target=HeatTarget.celsius(target_temp),
            heat_mode=HeatMode.HEAT_ON)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)
        from libpurecool.const import FocusMode
        if fan_mode == STATE_FOCUS:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_ON)
        elif fan_mode == STATE_DIFFUSE:
            self._device.set_configuration(focus_mode=FocusMode.FOCUS_OFF)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s heat mode %s", self.name, operation_mode)
        from libpurecool.const import HeatMode
        if operation_mode == STATE_HEAT:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_ON)
        elif operation_mode == STATE_COOL:
            self._device.set_configuration(heat_mode=HeatMode.HEAT_OFF)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 37
