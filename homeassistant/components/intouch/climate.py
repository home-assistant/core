"""Support for a Room thermostat attached to an Intouch Lan2RF gateway."""
import asyncio
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import (ATTR_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTOUCH_SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

INTOUCH_MAX_TEMP = 28.0
INTOUCH_MIN_TEMP = 4.0


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up an Intouch climate entity."""
    client = hass.data[DOMAIN]['client']

    water_heaters = await client.heaters
    await water_heaters[0].update()
    water_heater = water_heaters[0]

    async_add_entities(
        [InTouchClimate(client, water_heater.rooms[0])
    ])


class InTouchClimate(ClimateDevice):
    """Representation of an InTouch climate device."""

    def __init__(self, client, room):
        """Initialize the climate device."""
        self._client = client
        self._objref = room
        self._name = 'Room'

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._connect)

    @callback
    def _connect(self, packet):
        if packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {'status': self._objref.status}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._objref.room_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._objref.override  # self._objref.setpoint

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return INTOUCH_MIN_TEMP

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return INTOUCH_MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return INTOUCH_SUPPORT_FLAGS

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature for this zone."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._objref.set_override(temperature)

    @property
    def should_poll(self) -> bool:
        """Return True as this device should never be polled."""
        return False
