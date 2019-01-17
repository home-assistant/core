"""
Support for switches through the SmartThings cloud API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/smartthings.switch/
"""
from homeassistant.components.switch import ToggleEntity

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

DEPENDENCIES = ['smartthings']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add switches for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [SmartThingsSwitch(device) for device in broker.switches])


class SmartThingsSwitch(SmartThingsEntity, ToggleEntity):
    """Define a SmartThings switch."""

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._device.switch_off(True)
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._device.switch_on(True)
        self.async_schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.status.switch
