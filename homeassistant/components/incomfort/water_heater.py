"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""
import asyncio
import logging

from homeassistant.components.water_heater import WaterHeaterDevice
from homeassistant.const import TEMP_CELSIUS

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

HEATER_SUPPORT_FLAGS = 0

HEATER_MAX_TEMP = 80.0
HEATER_MIN_TEMP = 30.0

HEATER_NAME = 'Boiler'
HEATER_ATTRS = [
    'display_code', 'display_text', 'fault_code', 'is_burning', 'is_failed',
    'is_pumping', 'is_tapping', 'heater_temp', 'tap_temp', 'pressure']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up an InComfort/Intouch water_heater device."""
    client = hass.data[DOMAIN]['client']
    heater = hass.data[DOMAIN]['heater']

    async_add_entities([
        IncomfortWaterHeater(client, heater)], update_before_add=True)


class IncomfortWaterHeater(WaterHeaterDevice):
    """Representation of an InComfort/Intouch water_heater device."""

    def __init__(self, client, heater):
        """Initialize the water_heater device."""
        self._client = client
        self._heater = heater

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return HEATER_NAME

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        state = {k: self._heater.status[k]
                 for k in self._heater.status if k in HEATER_ATTRS}
        return state

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._heater.is_tapping:
            return self._heater.tap_temp
        return self._heater.heater_temp

    @property
    def min_temp(self):
        """Return max valid temperature that can be set."""
        return HEATER_MIN_TEMP

    @property
    def max_temp(self):
        """Return max valid temperature that can be set."""
        return HEATER_MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return HEATER_SUPPORT_FLAGS

    @property
    def current_operation(self):
        """Return the current operation mode."""
        if self._heater.is_failed:
            return "Failed ({})".format(self._heater.fault_code)

        return self._heater.display_text

    async def async_update(self):
        """Get the latest state data from the gateway."""
        try:
            await self._heater.update()

        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update failed, message: %s", err)
