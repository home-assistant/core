"""
Support for Anova sous-vide machines.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging

from homeassistant.components.sous_vide import SousVideEntity
from homeassistant.const import (
    PRECISION_WHOLE, STATE_OFF, STATE_ON, TEMP_CELSIUS)
from homeassistant.util import temperature as temp

_LOGGER = logging.getLogger(__name__)

DEMO_ENTITY_NAME = 'demo_cooker'
DEFAULT_UNIT = TEMP_CELSIUS
DEFAULT_PRECISION = PRECISION_WHOLE
DEFAULT_MIN_TEMP_IN_C = 15
DEFAULT_MAX_TEMP_IN_C = 90
DEFAULT_TARGET_TEMP_IN_C = 60
DEFAULT_CURRENT_TEMP_IN_C = 20
HEAT_DEGREES_PER_UPDATE_IN_C = 1.6
COOL_DEGREES_PER_UPDATE_IN_C = 0.8


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform setup for the platform."""
    add_devices([DemoSousVideEntity(DEMO_ENTITY_NAME)])


class DemoSousVideEntity(SousVideEntity):  # pylint: disable=too-many-instance-attributes; # noqa: E501
    """Representation of an demo sous-vide cooker."""

    def __init__(self, name, unit=DEFAULT_UNIT, precision=DEFAULT_PRECISION):
        """Create a new instance of AnovaEntity."""
        self._name = name
        self._state = STATE_OFF
        self._unit = unit
        self._precision = precision
        self._min_temp = temp.convert(
            DEFAULT_MIN_TEMP_IN_C, TEMP_CELSIUS, self._unit)
        self._max_temp = temp.convert(
            DEFAULT_MAX_TEMP_IN_C, TEMP_CELSIUS, self._unit)
        self._target_temp = temp.convert(
            DEFAULT_TARGET_TEMP_IN_C, TEMP_CELSIUS, self._unit)
        self._temp = temp.convert(
            DEFAULT_CURRENT_TEMP_IN_C, TEMP_CELSIUS, self._unit)

    @property
    def name(self):
        """Return the name of the cooker."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the cooker."""
        return self._unit

    @property
    def precision(self):
        """Return the precision of the cooker's temperature measurement."""
        return self._precision

    @property
    def current_temperature(self) -> float:
        """Return the cooker's current temperature in Celsius."""
        return self._temp

    @property
    def target_temperature(self) -> float:
        """Return the cooker's target temperature in Celsius."""
        return self._target_temp

    @property
    def min_temperature(self) -> float:
        """Return the minimum target temperature of the cooker in Celsius."""
        return self._min_temp

    @property
    def max_temperature(self) -> float:
        """Return the maximum target temperature of the cooker in Celsius."""
        return self._max_temp

    @property
    def is_on(self) -> bool:
        """Return True if the cooker is on."""
        return self._state == STATE_ON

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
        # Simulate heating and cooling from a device.
        if self._state == STATE_ON:
            temp_delta_in_c = HEAT_DEGREES_PER_UPDATE_IN_C
        else:
            temp_delta_in_c = -COOL_DEGREES_PER_UPDATE_IN_C
        temp_delta = temp.convert(
            temp_delta_in_c, TEMP_CELSIUS, self._unit, True)
        self._temp = max(min(self._temp + temp_delta,
                             self.target_temperature), self.min_temperature)
