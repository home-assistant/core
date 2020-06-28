"""Support for Proliphix NT10e Thermostats."""
import proliphix
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_TENTHS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

ATTR_FAN = "fan"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Proliphix thermostats."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    pdp = proliphix.PDP(host, username, password)
    pdp.update()

    add_entities([ProliphixThermostat(pdp)], True)


class ProliphixThermostat(ClimateEntity):
    """Representation a Proliphix thermostat."""

    def __init__(self, pdp):
        """Initialize the thermostat."""
        self._pdp = pdp
        self._name = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def should_poll(self):
        """Set up polling needed for thermostat."""
        return True

    def update(self):
        """Update the data from the thermostat."""
        self._pdp.update()
        self._name = self._pdp.name

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system.

        Proliphix temperature values are passed back and forth in the
        API as tenths of degrees F (i.e. 690 for 69 degrees).
        """
        return PRECISION_TENTHS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {ATTR_FAN: self._pdp.fan_state}

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._pdp.cur_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._pdp.setback

    @property
    def hvac_action(self):
        """Return the current state of the thermostat."""
        state = self._pdp.hvac_state
        if state == 1:
            return CURRENT_HVAC_OFF
        if state in (3, 4, 5):
            return CURRENT_HVAC_HEAT
        if state in (6, 7):
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_IDLE

    @property
    def hvac_mode(self):
        """Return the current state of the thermostat."""
        if self._pdp.is_heating:
            return HVAC_MODE_HEAT
        if self._pdp.is_cooling:
            return HVAC_MODE_COOL
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return []

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._pdp.setback = temperature
