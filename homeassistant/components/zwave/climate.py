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
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
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


# Device is in manufacturer specific mode (e.g. setting the valve manually)
PRESET_MANUFACTURER_SPECIFIC = "Manufacturer Specific"

WORKAROUND_ZXT_120 = "zxt_120"

DEVICE_MAPPINGS = {REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120}

HVAC_STATE_MAPPINGS = {
    "off": HVAC_MODE_OFF,
    "heat": HVAC_MODE_HEAT,
    "heat mode": HVAC_MODE_HEAT,
    "heat (default)": HVAC_MODE_HEAT,
    "aux heat": HVAC_MODE_HEAT,
    "furnace": HVAC_MODE_HEAT,
    "fan only": HVAC_MODE_FAN_ONLY,
    "dry air": HVAC_MODE_DRY,
    "moist air": HVAC_MODE_DRY,
    "cool": HVAC_MODE_COOL,
    "heat_cool": HVAC_MODE_HEAT_COOL,
    "auto": HVAC_MODE_HEAT_COOL,
}

HVAC_CURRENT_MAPPINGS = {
    "idle": CURRENT_HVAC_IDLE,
    "heat": CURRENT_HVAC_HEAT,
    "pending heat": CURRENT_HVAC_IDLE,
    "heating": CURRENT_HVAC_HEAT,
    "cool": CURRENT_HVAC_COOL,
    "pending cool": CURRENT_HVAC_IDLE,
    "cooling": CURRENT_HVAC_COOL,
    "fan only": CURRENT_HVAC_FAN,
    "vent / economiser": CURRENT_HVAC_FAN,
    "off": CURRENT_HVAC_OFF,
}

PRESET_MAPPINGS = {
    "full power": PRESET_BOOST,
    "manufacturer specific": PRESET_MANUFACTURER_SPECIFIC,
}

DEFAULT_HVAC_MODES = [
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
]


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
        self._default_hvac_mode = None
        self._preset_mapping = None
        self._preset_list = None
        self._preset_mode = None
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
        if self._preset_list:
            support |= SUPPORT_PRESET_MODE
        return support

    def update_properties(self):
        """Handle the data changes for node values."""
        # Operation Mode
        if self.values.mode:
            self._hvac_list = []
            self._hvac_mapping = {}
            self._preset_list = []
            self._preset_mapping = {}

            mode_list = self.values.mode.data_items
            if mode_list:
                for mode in mode_list:
                    ha_mode = HVAC_STATE_MAPPINGS.get(str(mode).lower())
                    ha_preset = PRESET_MAPPINGS.get(str(mode).lower())
                    if ha_mode and ha_mode not in self._hvac_mapping:
                        self._hvac_mapping[ha_mode] = mode
                        self._hvac_list.append(ha_mode)
                    elif ha_preset and ha_preset not in self._preset_mapping:
                        self._preset_mapping[ha_preset] = mode
                        self._preset_list.append(ha_preset)
                    else:
                        # If nothing matches
                        self._preset_list.append(mode)

            # Default operation mode
            for mode in DEFAULT_HVAC_MODES:
                if mode in self._hvac_mapping.keys():
                    self._default_hvac_mode = self._hvac_mapping.get(mode)
                    break

            if self._preset_list:
                # Presets are supported
                self._preset_list.append(PRESET_NONE)

            current_mode = self.values.mode.data
            _hvac_temp = next(
                (
                    key
                    for key, value in self._hvac_mapping.items()
                    if value == current_mode
                ),
                None,
            )

            if _hvac_temp is None:
                # The current mode is not a hvac mode
                if (
                    "heat" in current_mode.lower()
                    and HVAC_MODE_HEAT in self._hvac_mapping.values()
                ):
                    # The current preset modes maps to HVAC_MODE_HEAT
                    self._hvac_mode = next(
                        (
                            key
                            for key, value in self._hvac_mapping.items()
                            if value == HVAC_MODE_HEAT
                        )
                    )
                elif (
                    "cool" in current_mode.lower()
                    and HVAC_MODE_COOL in self._hvac_mapping.values()
                ):
                    # The current preset modes maps to HVAC_MODE_COOL
                    self._hvac_mode = next(
                        (
                            key
                            for key, value in self._hvac_mapping.items()
                            if value == HVAC_MODE_COOL
                        )
                    )
                else:
                    # The current preset modes maps to self._default_hvac_mode
                    self._hvac_mode = next(
                        (
                            key
                            for key, value in self._hvac_mapping.items()
                            if value == self._default_hvac_mode
                        )
                    )
                self._preset_mode = next(
                    (
                        key
                        for key, value in self._preset_mapping.items()
                        if value == current_mode
                    ),
                    current_mode,
                )
            else:
                # The current mode is a hvac mode
                self._hvac_mode = _hvac_temp
                self._preset_mode = PRESET_NONE

        _LOGGER.debug("self._hvac_list=%s", self._hvac_list)
        _LOGGER.debug("self._hvac_mode=%s", self._hvac_mode)
        _LOGGER.debug("self._default_hvac_mode=%s", self._default_hvac_mode)
        _LOGGER.debug("self._hvac_action=%s", self._hvac_action)
        _LOGGER.debug("self._preset_list=%s", self._preset_list)
        _LOGGER.debug("self._preset_mode=%s", self._preset_mode)

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
            self._hvac_action = HVAC_CURRENT_MAPPINGS.get(str(mode).lower(), mode)

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
        return self._default_hvac_mode

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
    def preset_mode(self):
        """Return preset operation ie. eco, away.

        Need to be one of PRESET_*.
        """
        if self.values.mode:
            return self._preset_mode
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return the list of available preset operation modes.

        Need to be a subset of PRESET_MODES.
        """
        if self.values.mode:
            return self._preset_list
        return []

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug("Set temperature to %s", kwargs.get(ATTR_TEMPERATURE))
        if kwargs.get(ATTR_TEMPERATURE) is None:
            return
        self.values.primary.data = kwargs.get(ATTR_TEMPERATURE)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.debug("Set fan mode to %s", fan_mode)
        if not self.values.fan_mode:
            return
        self.values.fan_mode.data = fan_mode

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("Set hvac_mode to %s", hvac_mode)
        if not self.values.mode:
            return
        self.values.mode.data = self._hvac_mapping.get(hvac_mode, hvac_mode)

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        _LOGGER.debug("Set preset_mode to %s", preset_mode)
        if not self.values.mode:
            return
        if preset_mode == PRESET_NONE:
            # Activate the current hvac mode
            self.update_properties()
            self.values.mode.data = self._hvac_mapping.get(self.hvac_mode)
        else:
            self.values.mode.data = self._preset_mapping.get(preset_mode, preset_mode)

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        _LOGGER.debug("Set swing_mode to %s", swing_mode)
        if self._zxt_120 == 1:
            if self.values.zxt_120_swing_mode:
                self.values.zxt_120_swing_mode.data = swing_mode
