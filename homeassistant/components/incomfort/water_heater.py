"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""
import asyncio
import logging

from homeassistant.components.water_heater import WaterHeaterDevice
from homeassistant.const import TEMP_CELSIUS

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

INCOMFORT_SUPPORT_FLAGS = 0

INCOMFORT_MAX_TEMP = 80.0
INCOMFORT_MIN_TEMP = 30.0

BOILER_NAME = 'Boiler'


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up an InComfort/Intouch water_heater device."""
    client = hass.data[DOMAIN]['client']
    heater = hass.data[DOMAIN]['heater']

    async_add_entities([
        IncomfortWaterHeater(client, heater)], update_before_add=True)


class IncomfortWaterHeater(WaterHeaterDevice):
    """Representation of an InComfort/Intouch water_heater device."""

    def __init__(self, client, boiler):
        """Initialize the water_heater device."""
        self._client = client
        self._boiler = boiler

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return BOILER_NAME

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        keys = ['nodenr', 'rf_message_rssi', 'rfstatus_cntr', 'room_1',
                'room_2']
        state = {k: self._boiler.status[k]
                 for k in self._boiler.status if k not in keys}
        return {'status': state}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._boiler.is_tapping:
            return self._boiler.tap_temp
        return self._boiler.heater_temp

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return INCOMFORT_MIN_TEMP

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return INCOMFORT_MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return INCOMFORT_SUPPORT_FLAGS

    @property
    def current_operation(self):
        """Return the current operation mode."""
        if self._boiler.is_failed:
            return "Failed ({})".format(self._boiler.fault_code)

        return self._boiler.display_text

    async def async_update(self):
        """Get the latest state data from the gateway."""
        try:
            await self._boiler.update()

        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update for failed, message: %s", err)
