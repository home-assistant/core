"""Support for Satel Integra modifiable outputs represented as switches."""
import asyncio
import logging


from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    CONF_DEVICE_CODE, CONF_SWITCHABLE_OUTPUTS, CONF_ZONE_NAME,
    DATA_SATEL, SIGNAL_OUTPUTS_UPDATED)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['satel_integra']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Satel Integra switch devices."""
    if not discovery_info:
        return

    configured_zones = discovery_info[CONF_SWITCHABLE_OUTPUTS]

    devices = []

    for zone_num, device_config_data in configured_zones.items():
        zone_name = device_config_data[CONF_ZONE_NAME]

        device = SatelIntegraSwitch(
            zone_num, zone_name, discovery_info[CONF_DEVICE_CODE])
        devices.append(device)

    async_add_entities(devices)


class SatelIntegraSwitch(SwitchDevice):
    """Representation of an Satel switch."""

    def __init__(self, device_number, device_name, code):
        """Initialize the binary_sensor."""
        self._device_number = device_number
        self._name = device_name
        self._state = False
        self._code = code

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_OUTPUTS_UPDATED, self._devices_updated)

    @callback
    def _devices_updated(self, zones):
        """Update switch state, if needed."""
        _LOGGER.debug("Update switch name: %s zones: %s.", self._name, zones)
        if self._device_number in zones:
            new_state = self._read_state()
            _LOGGER.debug("New state: %s", new_state)
            if new_state != self._state:
                self._state = new_state
                self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.debug("Switch: %s status: %s,"
                      " turning on", self._name, self._state)
        await self.hass.data[DATA_SATEL]\
                  .set_output(self._code, self._device_number, True)
        await asyncio.sleep(0.3)
        self._state = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Switch name: %s status: %s,"
                      " turning off", self._name, self._state)
        await self.hass.data[DATA_SATEL]\
                  .set_output(self._code, self._device_number, False)
        await asyncio.sleep(0.3)
        self._state = False
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        self._state = self._read_state()
        return self._state

    def _read_state(self):
        """Read state of the device."""
        if self._device_number in\
                self.hass.data[DATA_SATEL].violated_outputs:
                return True
        else:
                return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Don't poll."""
        return False
