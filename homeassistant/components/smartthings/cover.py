"""Support for covers through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence

from pysmartthings import Attribute, Capability

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_SHADE,
    DOMAIN as COVER_DOMAIN,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import ATTR_BATTERY_LEVEL

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

VALUE_TO_STATE = {
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "partially open": STATE_OPEN,
    "unknown": None,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add covers for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsCover(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, COVER_DOMAIN)
        ],
        True,
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    min_required = [
        Capability.door_control,
        Capability.garage_door_control,
        Capability.window_shade,
    ]
    # Must have one of the min_required
    if any(capability in capabilities for capability in min_required):
        # Return all capabilities supported/consumed
        return min_required + [Capability.battery, Capability.switch_level]

    return None


class SmartThingsCover(SmartThingsEntity, CoverEntity):
    """Define a SmartThings cover."""

    def __init__(self, device):
        """Initialize the cover class."""
        super().__init__(device)
        self._device_class = None
        self._state = None
        self._state_attrs = None
        self._supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
        if Capability.switch_level in device.capabilities:
            self._supported_features |= SUPPORT_SET_POSITION

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

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if not self._supported_features & SUPPORT_SET_POSITION:
            return
        # Do not set_status=True as device will report progress.
        await self._device.set_level(kwargs[ATTR_POSITION], 0)

    async def async_update(self):
        """Update the attrs of the cover."""
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

        self._state_attrs = {}
        battery = self._device.status.attributes[Attribute.battery].value
        if battery is not None:
            self._state_attrs[ATTR_BATTERY_LEVEL] = battery

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._state == STATE_CLOSED:
            return True
        return None if self._state is None else False

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        if not self._supported_features & SUPPORT_SET_POSITION:
            return None
        return self._device.status.level

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return self._device_class

    @property
    def extra_state_attributes(self):
        """Get additional state attributes."""
        return self._state_attrs

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features
