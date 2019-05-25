"""Support for Satel Integra modifiable outputs represented as switches."""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    CONF_DEVICE_CODE, CONF_SWITCHABLE_OUTPUTS, CONF_ZONE_NAME,
    SIGNAL_OUTPUTS_UPDATED, DATA_SATEL)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['satel_integra']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Satel Integra switch devices."""
    if not discovery_info:
        return

    configured_zones = discovery_info[CONF_SWITCHABLE_OUTPUTS]
    controller = hass.data[DATA_SATEL]

    devices = []

    for zone_num, device_config_data in configured_zones.items():
        zone_name = device_config_data[CONF_ZONE_NAME]

        device = SatelIntegraSwitch(
            controller, zone_num, zone_name, discovery_info[CONF_DEVICE_CODE])
        devices.append(device)

    async_add_entities(devices)


class SatelIntegraSwitch(SwitchDevice):
    """Representation of an Satel switch."""

    def __init__(self, controller, device_number, device_name, code):
        """Initialize the binary_sensor."""
        self._device_number = device_number
        self._name = device_name
        self._state = False
        self._code = code
        self._satel = controller

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_OUTPUTS_UPDATED, self._devices_updated)

    @callback
    def _devices_updated(self, zones):
        """Update switch state, if needed."""
        _LOGGER.debug("Update switch name: %s zones: %s", self._name, zones)
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
        await self._satel.set_output(self._code, self._device_number, True)
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Switch name: %s status: %s,"
                      " turning off", self._name, self._state)
        await self._satel.set_output(self._code, self._device_number, False)
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        self._state = self._read_state()
        return self._state

    def _read_state(self):
        """Read state of the device."""
        return self._device_number in self._satel.violated_outputs

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Don't poll."""
        return False
