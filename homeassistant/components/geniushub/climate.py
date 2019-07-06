"""Support for Genius Hub climate devices."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_HEAT, STATE_MANUAL,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

GH_ZONES = ['radiator']

GH_SUPPORT_FLAGS = \
    SUPPORT_TARGET_TEMPERATURE | \
    SUPPORT_ON_OFF | \
    SUPPORT_OPERATION_MODE

GH_MAX_TEMP = 28.0
GH_MIN_TEMP = 4.0

# Genius Hub Zones support only Off, Override/Boost, Footprint & Timer modes
HA_OPMODE_TO_GH = {
    STATE_OFF: 'off',
    STATE_AUTO: 'timer',
    STATE_ECO: 'footprint',
    STATE_MANUAL: 'override',
}
GH_STATE_TO_HA = {
    'off': STATE_OFF,
    'timer': STATE_AUTO,
    'footprint': STATE_ECO,
    'away': None,
    'override': STATE_MANUAL,
    'early': STATE_HEAT,
    'test': None,
    'linked': None,
    'other': None,
}
# temperature is repeated here, as it gives access to high-precision temps
GH_STATE_ATTRS = ['temperature', 'type', 'occupied', 'override']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius Hub climate entities."""
    client = hass.data[DOMAIN]['client']

    async_add_entities([GeniusClimateZone(client, z)
                        for z in client.hub.zone_objs if z.type in GH_ZONES])


class GeniusClimateZone(ClimateDevice):
    """Representation of a Genius Hub climate device."""

    def __init__(self, client, zone):
        """Initialize the climate device."""
        self._client = client
        self._zone = zone

        # Only some zones have movement detectors, which allows footprint mode
        op_list = list(HA_OPMODE_TO_GH)
        if not hasattr(self._zone, 'occupied'):
            op_list.remove(STATE_ECO)
        self._operation_list = op_list
        self._supported_features = GH_SUPPORT_FLAGS

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        tmp = self._zone.__dict__.items()
        return {'status': {k: v for k, v in tmp if k in GH_STATE_ATTRS}}

    @property
    def should_poll(self) -> bool:
        """Return False as the geniushub devices should not be polled."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend UI."""
        return "mdi:radiator"

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._zone.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._zone.setpoint

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return GH_MIN_TEMP

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return GH_MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return GH_STATE_TO_HA[self._zone.mode]

    @property
    def is_on(self):
        """Return True if the device is on."""
        return self._zone.mode != HA_OPMODE_TO_GH[STATE_OFF]

    async def async_set_operation_mode(self, operation_mode):
        """Set a new operation mode for this zone."""
        await self._zone.set_mode(HA_OPMODE_TO_GH[operation_mode])

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature for this zone."""
        await self._zone.set_override(kwargs.get(ATTR_TEMPERATURE), 3600)

    async def async_turn_on(self):
        """Turn on this heating zone.

        Set a Zone to Footprint mode if they have a Room sensor, and to Timer
        mode otherwise.
        """
        mode = STATE_ECO if hasattr(self._zone, 'occupied') else STATE_AUTO
        await self._zone.set_mode(HA_OPMODE_TO_GH[mode])

    async def async_turn_off(self):
        """Turn off this heating zone (i.e. to frost protect)."""
        await self._zone.set_mode(HA_OPMODE_TO_GH[STATE_OFF])
