"""Support for Lutron Caseta switches."""

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta switch platform.

    Adds switches from the Caseta bridge associated with the config_entry as
    switch entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    bridge_device = data.bridge_device
    switch_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        LutronCasetaLight(switch_device, bridge, bridge_device)
        for switch_device in switch_devices
    )


class LutronCasetaLight(LutronCasetaDeviceUpdatableEntity, SwitchEntity):
    """Representation of a Lutron Caseta switch."""

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._smartbridge.turn_on(self.device_id)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._smartbridge.turn_off(self.device_id)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device["current_state"] > 0
