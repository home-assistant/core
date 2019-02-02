"""
Support for fans through the SmartThings cloud API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/smartthings.fan/
"""

from homeassistant.components.fan import (
    SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF, SUPPORT_SET_SPEED,
    FanEntity)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

DEPENDENCIES = ['smartthings']

VALUE_TO_SPEED = {
    0: SPEED_OFF,
    1: SPEED_LOW,
    2: SPEED_MEDIUM,
    3: SPEED_HIGH,
}

SPEED_TO_VALUE = {
    SPEED_OFF: 0,
    SPEED_LOW: 1,
    SPEED_MEDIUM: 2,
    SPEED_HIGH: 3,
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add fans for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [SmartThingsFan(device) for device in broker.devices.values()
         if is_fan(device)])


def is_fan(device):
    """Determine if the device should be represented as a fan."""
    from pysmartthings import Capability
    # Must have switch and fan_speed
    return all(capability in device.capabilities
               for capability in [Capability.switch, Capability.fan_speed])


class SmartThingsFan(SmartThingsEntity, FanEntity):
    """Define a SmartThings Fan."""

    def __init__(self, device):
        """Initialize a SmartThingsFan."""
        super().__init__(device)
        self._supported_features = SUPPORT_SET_SPEED

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        value = SPEED_TO_VALUE[speed]
        await self._device.set_fan_speed(value, set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the fan on."""
        if speed is not None:
            value = SPEED_TO_VALUE[speed]
            await self._device.set_fan_speed(value, set_status=True)
        else:
            await self._device.switch_on(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self._device.switch_off(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._device.status.switch

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return VALUE_TO_SPEED[self._device.status.fan_speed]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features
