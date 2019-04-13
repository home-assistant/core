"""Supports Genius hub to provide climate controls."""
import logging

from asyncio import TimeoutError

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_HEAT, STATE_IDLE, STATE_MANUAL,
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

# Genius supports only Off, Override/Boost, Footprint & Timer modes
HA_OPMODE_TO_GH = {
    STATE_AUTO: 'timer',
    STATE_ECO: 'footprint',
    STATE_MANUAL: 'override',
}
GH_STATE_TO_HA = {
    'off': None,
    'timer': STATE_AUTO,
    'footprint': STATE_ECO,
    'away': None,
    'override': STATE_MANUAL,
    'early': STATE_HEAT,
    'test': None,
    'linked': None,
    'other': None,
}
GH_DEVICE_STATE_ATTRS = ['temperature', 'type', 'occupied', 'override']          # TODO: add 'schedule'

async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius hub climate devices."""
    client = hass.data[DOMAIN]['client']

    zones = []
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

        _LOGGER.debug("GeniusClimate(): Found Zone(%s), name = %s", zone.id, zone.name)

        self._client = client
        self._objref = zone
        self._id = zone.id
        self._name = zone.name

        tmp = list(HA_OPMODE_TO_GH)
        if not self._objref.type != ZONE_TYPE[ZONE_TYPES.ControlSP]:             # TODO: should be: if no PIR
            tmp.remove(STATE_ECO)
        self._operation_list = tmp

        # self._current_temperature = None
        # self._target_temperature = None
        # self._mode = None

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
        state = {k: v for k, v in tmp if k in GH_DEVICE_STATE_ATTRS}

        return {'status': state}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._objref.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.warn("target_temperature(%s) = %s", self._id, self._objref.setpoint)
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
        return self._operation_list

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return GH_STATE_TO_HA.get(self._objref.mode)

    @property
    def is_on(self):
        """Return True if the device is on."""
        from geniushubclient.const import (
            IMODE_TO_MODE as ZONE_MODE,
            zone_modes as ZONE_MODES,
        )
        return self._objref.mode != ZONE_MODE[ZONE_MODES.Off]

    async def async_set_operation_mode(self, operation_mode):
        """Set a new operation mode for this zone."""
        # TODO: also change target temp to appropriate SP
        _LOGGER.error("self(%s).set_op_mode(operation_mode=%s", self._id, operation_mode)  # TODO: remove this

        # if operation_mode == STATE_MANUAL:
        #     temperature = self._objref.setpoint
        #     _LOGGER.warn("self._objref.set_override(3600, %s)", temperature)
        #     await self._objref.set_override(3600, temperature)  # 1 hour
        # else:
        _LOGGER.warn("self._objref.set_mode(HA_OPMODE_TO_GH.get(%s))", operation_mode)
        _LOGGER.warn("self._objref.set_mode(%s)", HA_OPMODE_TO_GH.get(operation_mode))
        await self._objref.set_mode(HA_OPMODE_TO_GH.get(operation_mode))

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature for this zone."""
        # TODO: also change target temp to new SP
        temperature = kwargs.get(ATTR_TEMPERATURE)
        duration = kwargs.get('duration', 3600)                                  # TODO: needs ATTR_something
        _LOGGER.error("self(%s).set_temp(temperature=%s, duration=%s)...",
                      self._id, temperature, duration)                           # TODO: remove this

        _LOGGER.warn("self._objref.set_override(%s, %s)", temperature, duration)
        await self._objref.set_override(temperature, duration)

    async def async_turn_on(self):
        """Turn on this heating zone."""
        # TODO: also change target temp to (scheduled) SP
        _LOGGER.error("self(%s).turn_on()", self._id)                            # TODO: remove this

        _LOGGER.warn("self._objref.set_mode(%s)", HA_OPMODE_TO_GH.get(STATE_AUTO))
        await self._objref.set_mode(HA_OPMODE_TO_GH.get(STATE_AUTO))

    async def async_turn_off(self):
        """Turn off this heating zone (i.e. to frost protect)."""
        # TODO: also change target temp to minimum SP
        _LOGGER.error("self(%s).turn_off()", self._id)                           # TODO: remove this
        from geniushubclient.const import (
            zone_modes as ZONE_MODES,
        )
        _LOGGER.warn("self._objref.set_mode(%s)", ZONE_MODES.Off)
        await self._objref.set_mode(ZONE_MODES.Off)

    async def async_update(self):
        """Get the latest data from the hub."""
        _LOGGER.error("self.(%s).update(): updating...", self._id)               # TODO: remove this

        try:
            _LOGGER.warn("self._objref.update()")
            await self._objref.update()

        except (AssertionError, TimeoutError) as err:
            _LOGGER.warning(
                "self.(%s).update(): Failed (maybe just arbitary), message: %s",
                self._id, err)

        else:
            _LOGGER.debug("self.(%s).update(): success!", self._id)              # TODO: remove this
