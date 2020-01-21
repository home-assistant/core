"""Support for fans through the SmartThings cloud API."""
from typing import Optional, Sequence

from pysmartthings import Capability

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

VALUE_TO_SPEED = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}
SPEED_TO_VALUE = {v: k for k, v in VALUE_TO_SPEED.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add fans for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsFan(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, "fan")
        ]
    )


def get_capabilities(capabilities: Sequence[str]) -> Optional[Sequence[str]]:
    """Return all capabilities supported if minimum required are present."""
    supported = [Capability.switch, Capability.fan_speed]
    # Must have switch and fan_speed
    if all(capability in capabilities for capability in supported):
        return supported


class SmartThingsFan(SmartThingsEntity, FanEntity):
    """Define a SmartThings Fan."""

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        value = SPEED_TO_VALUE[speed]
        await self._device.set_fan_speed(value, set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the fan on."""
        if speed is not None:
            value = SPEED_TO_VALUE[speed]
            await self._device.set_fan_speed(value, set_status=True)
        else:
            await self._device.switch_on(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self._device.switch_off(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

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
        return SUPPORT_SET_SPEED
