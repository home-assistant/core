import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ATTR_HVAC_ACTION, ATTR_HVAC_MODE, ATTR_MAX_TEMP, ATTR_MIN_TEMP, ATTR_PRESET_MODE, ATTR_SWING_MODE, ATTR_TARGET_TEMP_STEP, HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_HEAT, HVAC_MODE_OFF, PRESET_AWAY, PRESET_NONE, SUPPORT_PRESET_MODE, SUPPORT_SWING_MODE, SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_RANGE
from homeassistant.const import TEMPERATURE, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

class NikoThermostat(ClimateEntity):
    """Representation of a Niko Thermostat."""

    def __init__(self):
        """Initialize the thermostat."""
        self._name = "Niko Thermostat"
        self._temperature = None
        self._target_temperature = None
        self._hvac_mode = HVAC_MODE_OFF

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temperature = kwargs[ATTR_TEMPERATURE]
            # Add logic to update the temperature on the actual device
            _LOGGER.debug("Setting target temperature to %s", self._target_temperature)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        self._hvac_mode = hvac_mode
        # Add logic to update the mode on the actual device
        _LOGGER.debug("Setting HVAC mode to %s", self._hvac_mode)

    async def async_update(self):
        """Retrieve latest state."""
        # Add logic to fetch the latest state from the actual device
        _LOGGER.debug("Updating state")
