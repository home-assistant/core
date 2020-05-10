"""Support for Lutron Caseta switches."""
import logging

from homeassistant.components.switch import DOMAIN, SwitchEntity

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta switch platform.

    Adds switches from the Caseta bridge associated with the config_entry as
    switch entities.
    """

    entities = []
    bridge = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    switch_devices = bridge.get_devices_by_domain(DOMAIN)

    for switch_device in switch_devices:
        entity = LutronCasetaLight(switch_device, bridge)
        entities.append(entity)

    async_add_entities(entities, True)
    return True


class LutronCasetaLight(LutronCasetaDevice, SwitchEntity):
    """Representation of a Lutron Caseta switch."""

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._smartbridge.turn_on(self.device_id)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._smartbridge.turn_off(self.device_id)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device["current_state"] > 0

    async def async_update(self):
        """Update when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)
