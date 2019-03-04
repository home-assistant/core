"""
Supports Genius hub to provide climate controls.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/climate.geniushub/
"""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_ECO, STATE_HEAT, STATE_AUTO, STATE_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    SUPPORT_ON_OFF, SUPPORT_AWAY_MODE)
from homeassistant.components.geniushub import GENIUS_HUB
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS)

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'geniushub'


SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE \
    | SUPPORT_ON_OFF | SUPPORT_AWAY_MODE
# Genius supports the operation modes: Off, Override, Footprint and Timer
# To work with Alexa these MUST BE
#
#   climate.STATE_HEAT: 'HEAT',
#   climate.STATE_COOL: 'COOL',
#   climate.STATE_AUTO: 'AUTO',
#   climate.STATE_ECO: 'ECO',
#   climate.STATE_IDLE: 'OFF',
#   climate.STATE_FAN_ONLY: 'OFF',
#   climate.STATE_DRY: 'OFF',

# These needed to be mapped into HA modes:
# Off       => OFF      => STATE_IDLE   # Mode_Off: 1,
# Override  => HEAT     => STATE_HEAT # Mode_Boost: 16,
# Footprint => ECO      => STATE_ECO    # Mode_Footprint: 4,
# Timer     => AUTO     => STATE_AUTO   # Mode_Timer: 2,
# Away                      # Mode_Away: 8,
#
OPERATION_LIST = [STATE_IDLE, STATE_HEAT, STATE_ECO, STATE_AUTO]


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the Genius hub climate devices."""
    genius_hub = hass.data[GENIUS_HUB]
    await genius_hub.getjson('/zones')

    # Get the zones with a temperature
    climate_list = genius_hub.getClimateList()

    for zone in climate_list:
        async_add_entities([GeniusClimate(genius_hub, zone)])


class GeniusClimate(ClimateDevice):
    """Representation of a Genius Hub climate device."""

    def __init__(self, genius_hub, zone):
        """Initialize the climate device."""
        GeniusClimate._genius_hub = genius_hub
        self._name = zone['name']
        self._device_id = zone['iID']
        self._current_temperature = zone['current_temperature']
        self._target_temperature = zone['target_temperature']
        self._mode = zone['mode']
        self._is_active = zone['is_active']

    @property
    def state(self):
        """Return the current state."""
        if self._is_active:
            return STATE_ON

        return STATE_OFF

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return 4.0

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return 28.0

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def is_on(self):
        """Return true if the device is on."""
        if self._mode == "off":
            return False

        return True

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        if self._mode == "away":
            return True

        return False

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return self.get_current_operation_mode(self._mode)

    @staticmethod
    def get_current_operation_mode(mode):
        """Return the current operational mode."""
        mode_map = {
            'override': STATE_HEAT,
            'footprint': STATE_ECO,
            'timer': STATE_AUTO,
        }
        return mode_map.get(mode, STATE_IDLE)

    def get_operation_mode(self, operation_mode):
        """Coverts operation mode from Home Assistant to Genius Hub."""
        # These needed to be mapped into HA modes:
        # Off       => OFF      => STATE_IDLE   # Mode_Off: 1,
        # Override  => HEAT     => STATE_HEAT # Mode_Boost: 16,
        # Footprint => ECO      => STATE_ECO    # Mode_Footprint: 4,
        # Timer     => AUTO     => STATE_AUTO   # Mode_Timer: 2,
        # Away                      # Mode_Away: 8,
        #
        # OPERATION_LIST = [STATE_IDLE, STATE_HEAT, STATE_ECO, STATE_AUTO]
        operation_mode_map = {
            STATE_IDLE: {'mode': 'off', 'data': {'iMode': 1}},
            STATE_HEAT: {'mode': 'override', 'data':
                         {'iBoostTimeRemaining': 3600,
                          'iMode': 16,
                          'fBoostSP': self._target_temperature}},
            STATE_ECO: {'mode': 'footprint', 'data': {'iMode': 4}},
            STATE_AUTO: {'mode': 'timer', 'data': {'iMode': 2}}, }
        return operation_mode_map.get(operation_mode,
                                      {'mode': 'off', 'data': None})

    async def async_set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        data = self.get_operation_mode(operation_mode)
        self._mode = data['mode']
        if data['data'] is None:
            _LOGGER.error("Unknown mode")
            return

        await GeniusClimate._genius_hub.putjson(self._device_id, data['data'])

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self.async_set_operation_mode(STATE_HEAT)

    async def async_update(self):
        """Get the latest data from the hub."""
        what_zone = GeniusClimate._genius_hub.getZone(self._device_id)
        if what_zone:
            zone = GeniusClimate._genius_hub.GET_CLIMATE(what_zone)
            self._current_temperature = zone['current_temperature']
            self._target_temperature = zone['target_temperature']
            self._mode = zone['mode']
            self._is_active = zone['is_active']

    async def async_turn_on(self):
        """Turn on."""
<<<<<<< HEAD
        await self.async_set_operation_mode(STATE_AUTO)
        self._mode = "on"
=======
        await GeniusClimate._genius_hub.putjson(
            self._device_id, {"iMode": 2})
        self._mode = "timer"
>>>>>>> 77a9cb1cf800fcd6bbb8a9ecccb59e8231382c20

    async def async_turn_off(self):
        """Turn off."""
<<<<<<< HEAD
        await self.async_set_operation_mode(STATE_IDLE)
=======
        await GeniusClimate._genius_hub.putjson(
            self._device_id, {"iMode": 1})
>>>>>>> 77a9cb1cf800fcd6bbb8a9ecccb59e8231382c20
        self._mode = "off"
