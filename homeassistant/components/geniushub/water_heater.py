"""Support for Genius Hub water_heater devices."""
import asyncio
import logging

from homeassistant.components.water_heater import (
    WaterHeaterDevice,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS)

from . import DOMAIN

STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'

_LOGGER = logging.getLogger(__name__)

GH_WATER_HEATERS = ['hot water temperature']

GENIUSHUB_SUPPORT_FLAGS = \
    SUPPORT_TARGET_TEMPERATURE | \
    SUPPORT_OPERATION_MODE
# HA does not have SUPPORT_ON_OFF for water_heater

GENIUSHUB_MAX_TEMP = 80.0
GENIUSHUB_MIN_TEMP = 30.0

# Genius Hub HW supports only Off, Override/Boost & Timer modes
HA_OPMODE_TO_GH = {
    STATE_OFF: 'off',
    STATE_AUTO: 'timer',
    STATE_MANUAL: 'override',
}
GH_OPMODE_OFF = 'off'
GH_STATE_TO_HA = {
    'off': STATE_OFF,
    'timer': STATE_AUTO,
    'footprint': None,
    'away': None,
    'override': STATE_MANUAL,
    'early': None,
    'test': None,
    'linked': None,
    'other': None,
}

GH_DEVICE_STATE_ATTRS = ['type', 'override']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius Hub water_heater entities."""
    client = hass.data[DOMAIN]['client']

    entities = [GeniusWaterHeater(client, z)
                for z in client.hub.zone_objs if z.type in GH_WATER_HEATERS]

    async_add_entities(entities)


class GeniusWaterHeater(WaterHeaterDevice):
    """Representation of a Genius Hub water_heater device."""

    def __init__(self, client, boiler):
        """Initialize the water_heater device."""
        self._client = client
        self._boiler = boiler
        self._id = boiler.id
        self._name = boiler.name

        self._operation_list = list(HA_OPMODE_TO_GH)

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return self._boiler.name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        tmp = self._boiler.__dict__.items()
        state = {k: v for k, v in tmp if k in GH_DEVICE_STATE_ATTRS}

        return {'status': state}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._boiler.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._boiler.setpoint

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
        return GH_STATE_TO_HA.get(self._boiler.mode)

    async def async_set_operation_mode(self, operation_mode):
        """Set a new operation mode for this boiler."""
        await self._boiler.set_mode(HA_OPMODE_TO_GH.get(operation_mode))

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature for this boiler."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self._boiler.set_override(temperature, 3600)  # 1 hour

    async def async_update(self):
        """Get the latest data from the hub."""
        try:
            await self._boiler.update()
        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update for %s failed, message: %s",
                            self._id, err)
