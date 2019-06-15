"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import (ATTR_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

INTOUCH_SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

INTOUCH_MAX_TEMP = 30.0
INTOUCH_MIN_TEMP = 5.0


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up an InComfort/InTouch climate device."""
    client = hass.data[DOMAIN]['client']
    heater = hass.data[DOMAIN]['heater']

    async_add_entities([InComfortClimate(client, r) for r in heater.rooms])


class InComfortClimate(ClimateDevice):
    """Representation of an InComfort/InTouch climate device."""

    def __init__(self, client, room):
        """Initialize the climate device."""
        self._client = client
        self._room = room
        self._name = 'Room {}'.format(room.room_no)

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {'status': self._room.status}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._room.room_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._room.override

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
        await self._room.set_override(temperature)

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False
