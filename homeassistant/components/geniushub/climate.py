"""Supports Genius hub to provide climate controls."""
import asyncio
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_HEAT, STATE_MANUAL,
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
GH_OPMODE_OFF = 'off'
GH_STATE_TO_HA = {
    'timer': STATE_AUTO,
    'footprint': STATE_ECO,
    'away': None,
    'override': STATE_MANUAL,
    'early': STATE_HEAT,
    'test': None,
    'linked': None,
    'other': None,
}  # intentionally missing 'off': None
GH_DEVICE_STATE_ATTRS = ['temperature', 'type', 'occupied', 'override']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius hub climate devices."""
    client = hass.data[DOMAIN]['client']

    zones = []
    for zone in client.hub.zone_objs:
        if hasattr(zone, 'temperature'):
            zones.append(GeniusClimate(client, zone))

    async_add_entities(zones)


class GeniusClimate(ClimateDevice):
    """Representation of a Genius Hub climate device."""

    def __init__(self, client, zone):
        """Initialize the climate device."""
        self._client = client
        self._objref = zone
        self._id = zone.id
        self._name = zone.name

        # Only some zones have movement detectors, which allows footprint mode
        op_list = list(HA_OPMODE_TO_GH)
        if not hasattr(self._objref, 'occupied'):
            op_list.remove(STATE_ECO)
        self._operation_list = op_list

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._objref.name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
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
        return self._objref.mode in GH_STATE_TO_HA

    async def async_set_operation_mode(self, operation_mode):
        """Set a new operation mode for this zone."""
        await self._objref.set_mode(HA_OPMODE_TO_GH.get(operation_mode))

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature for this zone."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._objref.set_override(temperature, 3600)  # 1 hour

    async def async_turn_on(self):
        """Turn on this heating zone."""
        await self._objref.set_mode(HA_OPMODE_TO_GH.get(STATE_AUTO))

    async def async_turn_off(self):
        """Turn off this heating zone (i.e. to frost protect)."""
        await self._objref.set_mode(GH_OPMODE_OFF)

    async def async_update(self):
        """Get the latest data from the hub."""
        try:
            await self._objref.update()
        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update for %s failed, message: %s",
                            self._id, err)
