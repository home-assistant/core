"""
Support for Homekit climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (
    HomeKitEntity, KNOWN_ACCESSORIES)
from homeassistant.components.climate import (
    ClimateDevice, STATE_HEAT, STATE_COOL, STATE_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import TEMP_CELSIUS, STATE_OFF, ATTR_TEMPERATURE

DEPENDENCIES = ['homekit_controller']

_LOGGER = logging.getLogger(__name__)

# Map of Homekit operation modes to hass modes
MODE_HOMEKIT_TO_HASS = {
    0: STATE_OFF,
    1: STATE_HEAT,
    2: STATE_COOL,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit climate."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([HomeKitClimateDevice(accessory, discovery_info)], True)


class HomeKitClimateDevice(HomeKitEntity, ClimateDevice):
    """Representation of a Homekit climate device."""

    def __init__(self, *args):
        """Initialise the device."""
        super().__init__(*args)
        self._state = None
        self._current_mode = None
        self._valid_modes = []
        self._current_temp = None
        self._target_temp = None

    def update_characteristics(self, characteristics):
        """Synchronise device state with Home Assistant."""
        # pylint: disable=import-error
        from homekit.models.characteristics import CharacteristicsTypes

        for characteristic in characteristics:
            ctype = characteristic['type']
            if ctype == CharacteristicsTypes.HEATING_COOLING_CURRENT:
                self._state = MODE_HOMEKIT_TO_HASS.get(
                    characteristic['value'])
            if ctype == CharacteristicsTypes.HEATING_COOLING_TARGET:
                self._chars['target_mode'] = characteristic['iid']
                self._features |= SUPPORT_OPERATION_MODE
                self._current_mode = MODE_HOMEKIT_TO_HASS.get(
                    characteristic['value'])
                self._valid_modes = [MODE_HOMEKIT_TO_HASS.get(
                    mode) for mode in characteristic['valid-values']]
            elif ctype == CharacteristicsTypes.TEMPERATURE_CURRENT:
                self._current_temp = characteristic['value']
            elif ctype == CharacteristicsTypes.TEMPERATURE_TARGET:
                self._chars['target_temp'] = characteristic['iid']
                self._features |= SUPPORT_TARGET_TEMPERATURE
                self._target_temp = characteristic['value']

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        characteristics = [{'aid': self._aid,
                            'iid': self._chars['target_temp'],
                            'value': temp}]
        self.put_characteristics(characteristics)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['target_mode'],
                            'value': MODE_HASS_TO_HOMEKIT[operation_mode]}]
        self.put_characteristics(characteristics)

    @property
    def state(self):
        """Return the current state."""
        # If the device reports its operating mode as off, it sometimes doesn't
        # report a new state.
        if self._current_mode == STATE_OFF:
            return STATE_OFF

        if self._state == STATE_OFF and self._current_mode != STATE_OFF:
            return STATE_IDLE
        return self._state

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_mode

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._valid_modes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
