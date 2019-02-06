"""
Support for switches through the SmartThings cloud API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/smartthings.switch/
"""
from homeassistant.components.switch import SwitchDevice

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
        [SmartThingsSwitch(device) for device in broker.devices.values()
         if is_switch(device)])


def is_switch(device):
    """Determine if the device should be represented as a switch."""
    from pysmartthings import Capability

    # Must be able to be turned on/off.
    if Capability.switch not in device.capabilities:
        return False
    # Must not have a capability represented by other types.
    non_switch_capabilities = [
        Capability.color_control,
        Capability.color_temperature,
        Capability.fan_speed,
        Capability.switch_level
    ]
    if any(capability in device.capabilities
           for capability in non_switch_capabilities):
        return False

    return True


class SmartThingsSwitch(SmartThingsEntity, SwitchDevice):
    """Define a SmartThings switch."""

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._device.switch_off(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._device.switch_on(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.status.switch
