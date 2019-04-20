"""Support for Homekit climate devices."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_HUMIDITY)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)

# Map of Homekit operation modes to hass modes
MODE_HOMEKIT_TO_HASS = {
    0: STATE_OFF,
    1: STATE_HEAT,
    2: STATE_COOL,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

DEFAULT_VALID_MODES = list(MODE_HOMEKIT_TO_HASS)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit climate."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]
        add_entities([HomeKitClimateDevice(accessory, discovery_info)], True)


class HomeKitClimateDevice(HomeKitEntity, ClimateDevice):
    """Representation of a Homekit climate device."""

    def __init__(self, *args):
        """Initialise the device."""
        self._state = None
        self._current_mode = None
        self._valid_modes = []
        self._current_temp = None
        self._target_temp = None
        self._current_humidity = None
        self._target_humidity = None
        super().__init__(*args)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.HEATING_COOLING_CURRENT,
            CharacteristicsTypes.HEATING_COOLING_TARGET,
            CharacteristicsTypes.TEMPERATURE_CURRENT,
            CharacteristicsTypes.TEMPERATURE_TARGET,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET,
        ]

    def _setup_heating_cooling_target(self, characteristic):
        self._features |= SUPPORT_OPERATION_MODE

        if 'valid-values' in characteristic:
            valid_values = [
                val for val in DEFAULT_VALID_MODES
                if val in characteristic['valid-values']
            ]
        else:
            valid_values = DEFAULT_VALID_MODES
            if 'minValue' in characteristic:
                valid_values = [
                    val for val in valid_values
                    if val >= characteristic['minValue']
                ]
            if 'maxValue' in characteristic:
                valid_values = [
                    val for val in valid_values
                    if val <= characteristic['maxValue']
                ]

        self._valid_modes = [
            MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values
        ]

    def _setup_temperature_target(self, characteristic):
        self._features |= SUPPORT_TARGET_TEMPERATURE

    def _setup_relative_humidity_target(self, characteristic):
        self._features |= SUPPORT_TARGET_HUMIDITY

    def _update_heating_cooling_current(self, value):
        self._state = MODE_HOMEKIT_TO_HASS.get(value)

    def _update_heating_cooling_target(self, value):
        self._current_mode = MODE_HOMEKIT_TO_HASS.get(value)

    def _update_temperature_current(self, value):
        self._current_temp = value

    def _update_temperature_target(self, value):
        self._target_temp = value

    def _update_relative_humidity_current(self, value):
        self._current_humidity = value

    def _update_relative_humidity_target(self, value):
        self._target_humidity = value

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        characteristics = [{'aid': self._aid,
                            'iid': self._chars['temperature.target'],
                            'value': temp}]
        await self._accessory.put_characteristics(characteristics)

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['relative-humidity.target'],
                            'value': humidity}]
        await self._accessory.put_characteristics(characteristics)

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['heating-cooling.target'],
                            'value': MODE_HASS_TO_HOMEKIT[operation_mode]}]
        await self._accessory.put_characteristics(characteristics)

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
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

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
