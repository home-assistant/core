"""
Support for KNX thermostats.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/knx/

(c) 2016 Daniel Matuschek <info@open-homeautomation.com>
"""
import logging

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELSIUS

from homeassistant.components.knx import (
    KNXConfig, KNXMultiAddressDevice)

DEPENDENCIES = ["knx"]

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        KNXThermostat(hass, KNXConfig(config))
    ])


class KNXThermostat(KNXMultiAddressDevice, ThermostatDevice):
    """Representation of a KNX thermostat.

    A KNX thermostat will has the following parameters:
    - temperature (current temperature)
    - setpoint (target temperature in HASS terms)
    - hvac mode selection (comfort/night/frost protection)

    This version supports only polling. Messages from the KNX bus do not
    automatically update the state of the thermostat (to be implemented
    in future releases)
    """

    def __init__(self, hass, config):
        """Initialize the thermostat based on the given configuration."""
        KNXMultiAddressDevice.__init__(self, hass, config,
                                       ["temperature", "setpoint"],
                                       ["mode"])

        self._unit_of_measurement = TEMP_CELSIUS  # KNX always used celcius
        self._away = False  # not yet supported
        self._is_fan_on = False  # not yet supported

    @property
    def should_poll(self):
        """Polling is needed for the KNX thermostat."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        from knxip.conversion import knx2_to_float

        return knx2_to_float(self.value("temperature"))

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        from knxip.conversion import knx2_to_float

        return knx2_to_float(self.value("setpoint"))

    def set_temperature(self, temperature):
        """Set new target temperature."""
        from knxip.conversion import float_to_knx2

        self.set_value("setpoint", float_to_knx2(temperature))
        _LOGGER.debug("Set target temperature to %s", temperature)

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def is_fan_on(self):
        """Return true if the fan is on."""
        return self._is_fan_on

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False

    def turn_fan_on(self):
        """Turn fan on."""
        self._is_fan_on = True

    def turn_fan_off(self):
        """Turn fan off."""
        self._is_fan_on = False

    def set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        raise NotImplementedError()
