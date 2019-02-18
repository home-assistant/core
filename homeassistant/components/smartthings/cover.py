"""Support for covers through the SmartThings cloud API."""
from typing import Optional, Sequence

from homeassistant.components.cover import (
    DEVICE_CLASS_DOOR, DEVICE_CLASS_GARAGE, DEVICE_CLASS_SHADE,
    DOMAIN as COVER_DOMAIN, STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
    STATE_OPENING, SUPPORT_CLOSE, SUPPORT_OPEN, CoverDevice)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

DEPENDENCIES = ['smartthings']

VALUE_TO_STATE = {
    'closed': STATE_CLOSED,
    'closing': STATE_CLOSING,
    'open': STATE_OPEN,
    'opening': STATE_OPENING,
    'partially open': STATE_OPEN,
    'unknown': None
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add covers for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [SmartThingsCover(device) for device in broker.devices.values()
         if broker.any_assigned(device.device_id, COVER_DOMAIN)], True)


def get_capabilities(capabilities: Sequence[str]) -> Optional[Sequence[str]]:
    """Return all capabilities supported if minimum required are present."""
    from pysmartthings import Capability

    supported = [
        Capability.door_control,
        Capability.garage_door_control,
        Capability.window_shade
    ]
    # Must have one of the supported
    if any(capability in capabilities
           for capability in supported):
        return supported
    return None


class SmartThingsCover(SmartThingsEntity, CoverDevice):
    """Define a SmartThings cover."""

    def __init__(self, device):
        """Initialize the cover class."""
        super().__init__(device)
        self._device_class = None
        self._state = None

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        # Same command for all 3 supported capabilities
        await self._device.close(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        # Same for all capability types
        await self._device.open(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update the attrs of the cover."""
        from pysmartthings import Capability

        value = None
        if Capability.door_control in self._device.capabilities:
            self._device_class = DEVICE_CLASS_DOOR
            value = self._device.status.door
        elif Capability.window_shade in self._device.capabilities:
            self._device_class = DEVICE_CLASS_SHADE
            value = self._device.status.window_shade
        elif Capability.garage_door_control in self._device.capabilities:
            self._device_class = DEVICE_CLASS_GARAGE
            value = self._device.status.door
        self._state = VALUE_TO_STATE.get(value)

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return self._device_class

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def state(self) -> str:
        """Get the state of the cover."""
        return self._state
