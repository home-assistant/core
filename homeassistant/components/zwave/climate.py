"""Support for Z-Wave climate devices."""
# Because we do not compile openzwave on CI
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
DEFAULT_NAME = "Z-Wave Climate"

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120)
ATTR_OPERATING_STATE = "operating_state"
ATTR_FAN_STATE = "fan_state"

WORKAROUND_ZXT_120 = "zxt_120"

DEVICE_MAPPINGS = {REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120}

HVAC_STATE_MAPPINGS = {
    "Off": HVAC_MODE_OFF,
    "Heat": HVAC_MODE_HEAT,
    "Heat Mode": HVAC_MODE_HEAT,
    "Heat (Default)": HVAC_MODE_HEAT,
    "Aux Heat": HVAC_MODE_HEAT,
    "Furnace": HVAC_MODE_HEAT,
    "Fan Only": HVAC_MODE_FAN_ONLY,
    "Dry Air": HVAC_MODE_DRY,
    "Moist Air": HVAC_MODE_DRY,
    "Cool": HVAC_MODE_COOL,
    "Auto": HVAC_MODE_HEAT_COOL,
}


HVAC_CURRENT_MAPPINGS = {
    "Idle": CURRENT_HVAC_IDLE,
    "Heat": CURRENT_HVAC_HEAT,
    "Pending Heat": CURRENT_HVAC_IDLE,
    "Heating": CURRENT_HVAC_HEAT,
    "Cool": CURRENT_HVAC_COOL,
    "Pending Cool": CURRENT_HVAC_IDLE,
    "Cooling": CURRENT_HVAC_COOL,
    "Fan Only": CURRENT_HVAC_FAN,
    "Vent / Economiser": CURRENT_HVAC_FAN,
    "Off": CURRENT_HVAC_OFF,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old method of setting up Z-Wave climate devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Climate device from Config Entry."""

    @callback
    def async_add_climate(climate):
        """Add Z-Wave Climate Device."""
        async_add_entities([climate])

    async_dispatcher_connect(hass, "zwave_new_climate", async_add_climate)


def get_device(hass, values, **kwargs):
    """Create Z-Wave entity device."""
    temp_unit = hass.config.units.temperature_unit
    return ZWaveClimate(values, temp_unit)


class ZWaveClimate(ZWaveDeviceEntity, ClimateDevice):
    """Representation of a Z-Wave Climate device."""

    def __init__(self, values, temp_unit):
        """Initialize the Z-Wave climate device."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_action = None
        self._hvac_list = None
        self._hvac_mapping = None
        self._hvac_mode = None
        self._current_fan_mode = None
        self._fan_modes = None
        self._fan_state = None
        self._current_swing_mode = None
        self._swing_modes = None
        self._unit = temp_unit
        _LOGGER.debug("temp_unit is %s", self._unit)
        self._zxt_120 = None
        # Make sure that we have values for the key before converting to int
        if self.node.manufacturer_id.strip() and self.node.product_id.strip():
            specific_sensor_key = (
                int(self.node.manufacturer_id, 16),
                int(self.node.product_id, 16),
            )
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZXT_120:
                    _LOGGER.debug("Remotec ZXT-120 Zwave Thermostat workaround")
                    self._zxt_120 = 1
        self.update_properties()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = SUPPORT_TARGET_TEMPERATURE
        if self.values.fan_mode:
            support |= SUPPORT_FAN_MODE
        if self._zxt_120 == 1 and self.values.zxt_120_swing_mode:
            support |= SUPPORT_SWING_MODE
        return support

    def update_properties(self):
        """Handle the data changes for node values."""
        # Operation Mode
        if self.values.mode:
            self._hvac_list = []
            self._hvac_mapping = {}
            hvac_list = self.values.mode.data_items
            if hvac_list:
                for mode in hvac_list:
                    ha_mode = HVAC_STATE_MAPPINGS.get(mode)
                    if ha_mode and ha_mode not in self._hvac_mapping:
                        self._hvac_mapping[ha_mode] = mode
                        self._hvac_list.append(ha_mode)
                        continue
                    self._hvac_list.append(mode)
            current_mode = self.values.mode.data
            self._hvac_mode = next(
                (
                    key
                    for key, value in self._hvac_mapping.items()
                    if value == current_mode
                ),
                current_mode,
            )
        _LOGGER.debug("self._hvac_list=%s", self._hvac_list)
        _LOGGER.debug("self._hvac_action=%s", self._hvac_action)

        # Current Temp
        if self.values.temperature:
            self._current_temperature = self.values.temperature.data
            device_unit = self.values.temperature.units
            if device_unit is not None:
                self._unit = device_unit

        # Fan Mode
        if self.values.fan_mode:
            self._current_fan_mode = self.values.fan_mode.data
            fan_modes = self.values.fan_mode.data_items
            if fan_modes:
                self._fan_modes = list(fan_modes)
        _LOGGER.debug("self._fan_modes=%s", self._fan_modes)
        _LOGGER.debug("self._current_fan_mode=%s", self._current_fan_mode)
        # Swing mode
        if self._zxt_120 == 1:
            if self.values.zxt_120_swing_mode:
                self._current_swing_mode = self.values.zxt_120_swing_mode.data
                swing_modes = self.values.zxt_120_swing_mode.data_items
                if swing_modes:
                    self._swing_modes = list(swing_modes)
            _LOGGER.debug("self._swing_modes=%s", self._swing_modes)
            _LOGGER.debug("self._current_swing_mode=%s", self._current_swing_mode)
        # Set point
        if self.values.primary.data == 0:
            _LOGGER.debug(
                "Setpoint is 0, setting default to " "current_temperature=%s",
                self._current_temperature,
            )
            if self._current_temperature is not None:
                self._target_temperature = round((float(self._current_temperature)), 1)
        else:
            self._target_temperature = round((float(self.values.primary.data)), 1)

        # Operating state
        if self.values.operating_state:
            mode = self.values.operating_state.data
            self._hvac_action = HVAC_CURRENT_MAPPINGS.get(mode)

        # Fan operating state
        if self.values.fan_state:
            self._fan_state = self.values.fan_state.data

    @property
    def fan_mode(self):
        """Return the fan speed set."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return a list of available fan modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return the swing mode set."""
        return self._current_swing_mode

    @property
    def swing_modes(self):
        """Return a list of available swing modes."""
        return self._swing_modes

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._unit == "C":
            return TEMP_CELSIUS
        if self._unit == "F":
            return TEMP_FAHRENHEIT
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self.values.mode:
            return self._hvac_mode
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        if self.values.mode:
            return self._hvac_list
        return []

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return self._hvac_action

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is None:
            return
        self.values.primary.data = kwargs.get(ATTR_TEMPERATURE)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if not self.values.fan_mode:
            return
        self.values.fan_mode.data = fan_mode

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if not self.values.mode:
            return
        self.values.mode.data = self._hvac_mapping.get(hvac_mode, hvac_mode)

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if self._zxt_120 == 1:
            if self.values.zxt_120_swing_mode:
                self.values.zxt_120_swing_mode.data = swing_mode
