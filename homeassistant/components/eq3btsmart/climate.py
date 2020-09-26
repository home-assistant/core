"""Support for eQ-3 Bluetooth Smart thermostats."""
import logging

from bluepy.btle import BTLEException  # pylint: disable=import-error, no-name-in-module
import eq3bt as eq3  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    CONF_MAC,
    PRECISION_HALVES,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = "boost"

ATTR_STATE_WINDOW_OPEN = "window_open"
ATTR_STATE_VALVE = "valve"
ATTR_STATE_LOCKED = "is_locked"
ATTR_STATE_LOW_BAT = "low_battery"
ATTR_STATE_AWAY_END = "away_end"

EQ_TO_HA_HVAC = {
    eq3.Mode.Open: HVAC_MODE_HEAT,
    eq3.Mode.Closed: HVAC_MODE_OFF,
    eq3.Mode.Auto: HVAC_MODE_AUTO,
    eq3.Mode.Manual: HVAC_MODE_HEAT,
    eq3.Mode.Boost: HVAC_MODE_AUTO,
    eq3.Mode.Away: HVAC_MODE_HEAT,
}

HA_TO_EQ_HVAC = {
    HVAC_MODE_HEAT: eq3.Mode.Manual,
    HVAC_MODE_OFF: eq3.Mode.Closed,
    HVAC_MODE_AUTO: eq3.Mode.Auto,
}

EQ_TO_HA_PRESET = {eq3.Mode.Boost: PRESET_BOOST, eq3.Mode.Away: PRESET_AWAY}

HA_TO_EQ_PRESET = {PRESET_BOOST: eq3.Mode.Boost, PRESET_AWAY: eq3.Mode.Away}


DEVICE_SCHEMA = vol.Schema({vol.Required(CONF_MAC): cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): vol.Schema({cv.string: DEVICE_SCHEMA})}
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the eQ-3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_entities(devices, True)


class EQ3BTSmartThermostat(ClimateEntity):
    """Representation of an eQ-3 Bluetooth Smart thermostat."""

    def __init__(self, _mac, _name):
        """Initialize the thermostat."""
        # We want to avoid name clash with this module.
        self._name = _name
        self._thermostat = eq3.Thermostat(_mac)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self._thermostat.mode >= 0

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return eq3bt's precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Can not report temperature, so return target_temperature."""
        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._thermostat.target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._thermostat.target_temperature = temperature

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        if self._thermostat.mode < 0:
            return HVAC_MODE_OFF
        return EQ_TO_HA_HVAC[self._thermostat.mode]

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(HA_TO_EQ_HVAC.keys())

    def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if self.preset_mode:
            return
        self._thermostat.mode = HA_TO_EQ_HVAC[hvac_mode]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._thermostat.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._thermostat.max_temp

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        dev_specific = {
            ATTR_STATE_AWAY_END: self._thermostat.away_end,
            ATTR_STATE_LOCKED: self._thermostat.locked,
            ATTR_STATE_LOW_BAT: self._thermostat.low_battery,
            ATTR_STATE_VALVE: self._thermostat.valve_state,
            ATTR_STATE_WINDOW_OPEN: self._thermostat.window_open,
        }

        return dev_specific

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        return EQ_TO_HA_PRESET.get(self._thermostat.mode)

    @property
    def preset_modes(self):
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return list(HA_TO_EQ_PRESET.keys())

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_NONE:
            self.set_hvac_mode(HVAC_MODE_HEAT)
        self._thermostat.mode = HA_TO_EQ_PRESET[preset_mode]

    def update(self):
        """Update the data from the thermostat."""

        try:
            self._thermostat.update()
        except BTLEException as ex:
            _LOGGER.warning("Updating the state failed: %s", ex)
