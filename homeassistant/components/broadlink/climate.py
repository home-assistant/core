"""
Support for Chinese wifi thermostats (Floureon, Beok, Beca Energy).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.broadlink/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA, STATE_OFF
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_MAC,
    PRECISION_HALVES,
    TEMP_CELSIUS,
    CONF_HOST,
)
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Broadlink Thermostat"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_MAC): cv.string}
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the broadlink thermostat platform."""
    import BroadlinkWifiThermostat

    wifi_thermostat = BroadlinkWifiThermostat.Thermostat(
        config[CONF_MAC], config[CONF_HOST], DEFAULT_NAME
    )
    thermostats = [BroadlinkThermostat(wifi_thermostat)]

    add_entities(thermostats)


class BroadlinkThermostat(ClimateDevice):
    """Representation of a Broadlink Thermostat device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device
        device.set_time()

    @property
    def state(self):
        """Return climate state."""
        return self._device.state

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._device.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def is_on(self):
        """Return true if the device is on."""
        return not self._device.current_operation == STATE_OFF

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self._device.set_operation_mode("auto")
        elif hvac_mode == HVAC_MODE_HEAT:
            self._device.set_operation_mode("heat")
        elif hvac_mode == HVAC_MODE_OFF:
            self._device.set_operation_mode("off")

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))

    def update(self):
        """Update component data."""
        self._device.read_status()
