"""
Support for Anova sous-vide machines.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging
import random

from homeassistant.components.sous_vide import SousVideDevice
from homeassistant.const import (
    PRECISION_TENTHS, STATE_OFF, STATE_ON, TEMP_CELSIUS)
from homeassistant.util import temperature as temp_util

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform setup for the platform."""
    add_devices([DemoSousVideDevice('Sous_Vide')])


class DemoSousVideDevice(SousVideDevice):  # pylint: disable=too-many-instance-attributes; # noqa: E501
    """Representation of an demo sous-vide cooker."""

    _temp = 20
    _target_temp = 60
    _unit = TEMP_CELSIUS
    _state = STATE_OFF

    def __init__(self, name):
        """Create a new instance of AnovaEntity."""
        self._name = name

    @property
    def name(self):
        """Return the name of the cooker."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the cooker."""
        return self._unit

    @property
    def is_on(self) -> bool:
        """Return True if the cooker is on."""
        return self._state == STATE_ON

    @property
    def precision(self):
        """Return the precision of the cooker's temperature measurement."""
        return PRECISION_TENTHS

    @property
    def current_temperature(self) -> float:
        """Return the cooker's current temperature."""
        return self._temp

    @property
    def target_temperature(self) -> float:
        """Return the cooker's target temperature."""
        return self._target_temp

    @property
    def min_temperature(self) -> float:
        """Return the minimum target temperature of the cooker."""
        return round(temp_util.convert(15, TEMP_CELSIUS, self._unit), 2)

    @property
    def max_temperature(self) -> float:
        """Return the maximum target temperature of the cooker."""
        return round(temp_util.convert(90, TEMP_CELSIUS, self._unit), 2)

    def turn_on(self, **kwargs) -> None:
        """Turn the cooker on (starts cooking."""
        self._state = STATE_ON

    def turn_off(self, **kwargs) -> None:
        """Turn the cooker off (stops cooking)."""
        self._state = STATE_OFF

    def set_temp(self, temperature=None) -> None:
        """Set the target temperature of the cooker."""
        if temperature is not None:
            self._target_temp = max(
                min(temperature, self.max_temperature), self.min_temperature)

    def update(self):
        """Fetch state from the device."""

        # Simulate heating and cooling
        if self._state == STATE_ON:
            self._temp = min(self._temp + random.uniform(0.5, 2.0),
                             self.target_temperature)
        else:
            self._temp = max(self._temp - random.uniform(0.25, 1.0),
                             self.min_temperature)
