"""Supports Genius hub to provide climate controls."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_HEAT, STATE_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF)
from homeassistant.const import (
    ATTR_TEMPERATURE, TEMP_CELSIUS)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

GENIUSHUB_SUPPORT_FLAGS = \
    SUPPORT_TARGET_TEMPERATURE | \
    SUPPORT_ON_OFF | \
    SUPPORT_OPERATION_MODE

GENIUSHUB_MAX_TEMP = 28.0
GENIUSHUB_MIN_TEMP = 4.0

# Genius supports the operation modes: Off, Override/Boost, Footprint & Timer

# To work with Alexa these MUST BE
#   climate.STATE_HEAT: 'HEAT',
#   climate.STATE_COOL: 'COOL',
#   climate.STATE_AUTO: 'AUTO',
#   climate.STATE_ECO: 'ECO',
#   climate.STATE_IDLE: 'OFF',
#   climate.STATE_FAN_ONLY: 'OFF',
#   climate.STATE_DRY: 'OFF',

# These needed to be mapped into HA modes:
# Off       => OFF      => STATE_IDLE   # Mode_Off: 1,
# Override  => HEAT     => STATE_HEAT   # Mode_Boost: 16,
# Footprint => ECO      => STATE_ECO    # Mode_Footprint: 4,
# Timer     => AUTO     => STATE_AUTO   # Mode_Timer: 2,

"""Map between GeniusHub and Home Assistant"""
GENIUSHUB_STATE_TO_HA = {
    'off': STATE_IDLE,
    'timer': STATE_AUTO,
    'footprint': STATE_ECO,
    'away': None,
    'boost': STATE_HEAT,
    'early': STATE_HEAT,
    'test': None,
    'linked': None,
    'other': None,
}
HA_OPMODE_TO_GENIUSHUB = {
    STATE_AUTO: 'timer',
    STATE_ECO: 'footprint',
    STATE_HEAT: 'override',
    STATE_IDLE: 'off',
}


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius hub climate devices."""
    client = hass.data[DOMAIN]['client']

    zones = []
    #for zone in discovery_info:
    #    zones.append(GeniusClimate(client, zone))
    for zone in client.hub.zone_objs:
        if hasattr(zone, 'temperature'):
            zones.append(GeniusClimate(client, zone))

    async_add_entities(zones, update_before_add=False)


class GeniusClimate(ClimateDevice):
    """Representation of a Genius Hub climate device."""

    def __init__(self, client, zone):
        """Initialize the climate device."""
        from geniushubclient.const import (
            ITYPE_TO_TYPE as ZONE_TYPE,
            zone_types as ZONE_TYPES,
        )

        _LOGGER.warn("GeniusClimate(): Found Zone, id = %s [%s]", zone.id, zone.name)

        self._client = client
        self._objref = zone
        self._id = zone.id
        self._name = zone.name

        tmp = list(HA_OPMODE_TO_GENIUSHUB)
        if self._objref.type != ZONE_TYPE[ZONE_TYPES.ControlSP]:                 # TODO: actually, if no PIR
            tmp.remove(STATE_ECO)
        self._operation_list = tmp

        self._current_temperature = None
        self._target_temperature = None
        self._mode = None

        self._status = None # ????

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._objref.name

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the evohome Climate device.

        This is state data that is not available otherwise, due to the
        restrictions placed upon ClimateDevice properties, etc. by HA.
        """
        tmp = self._objref.__dict__.items()
        state = {k: v for k, v in tmp if k[:1] != '_'}

        _LOGGER.warn("device_state_attributes(%s [%s]) = %s", self._id, self._name, {'status': state})
        return {'status': state}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._objref.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._objref.setpoint

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return GENIUSHUB_MIN_TEMP

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return GENIUSHUB_MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return GENIUSHUB_SUPPORT_FLAGS

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        _LOGGER.warn("operation_list(%s [%s]) = %s", self._id, self._name, self._operation_list)
        return self._operation_list

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return GENIUSHUB_STATE_TO_HA.get(self._objref.mode)

    @property
    def is_on(self):
        """Return true if the device is on."""
        from geniushubclient.const import (
            IMODE_TO_MODE as ZONE_MODE,
            zone_modes as ZONE_MODES,
        )
        return self._objref.mode != ZONE_MODE[ZONE_MODES.Off]

    async def async_set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        from geniushubclient.const import zone_modes
        op_mode = {
            STATE_AUTO: {'iMode': zone_modes.Timer},
            STATE_ECO:  {'iMode': zone_modes.Footprint},
            STATE_HEAT: {'iMode': zone_modes.Boost,
                         'iBoostTimeRemaining': 3600,
                         'fBoostSP': self._target_temperature},
            STATE_IDLE: {'iMode': zone_modes.Off},
        }.get(operation_mode)

#       await self._client.putjson(self._id, op_mode)

        self._mode = HA_OPMODE_TO_GENIUSHUB[operation_mode]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._target_temperature = temperature
        await self.async_set_operation_mode(STATE_HEAT)

    async def async_turn_on(self):
        """Turn on."""
        await self.async_set_operation_mode(STATE_AUTO)

    async def async_turn_off(self):
        """Turn off."""
        await self.async_set_operation_mode(STATE_IDLE)

    async def async_update(self):
        """Get the latest data from the hub."""
        pass
        # self._obj_ref.refresh()
