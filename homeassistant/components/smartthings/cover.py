"""Support for covers through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Attribute, Capability

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

VALUE_TO_STATE = {
    "closed": CoverState.CLOSED,
    "closing": CoverState.CLOSING,
    "open": CoverState.OPEN,
    "opening": CoverState.OPENING,
    "partially open": CoverState.OPEN,
    "unknown": None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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
        return [
            *min_required,
            Capability.battery,
            Capability.switch_level,
            Capability.window_shade_level,
        ]

    return None


class SmartThingsCover(SmartThingsEntity, CoverEntity):
    """Define a SmartThings cover."""

    def __init__(self, device):
        """Initialize the cover class."""
        super().__init__(device)
        self._current_cover_position = None
        self._state = None
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if (
            Capability.switch_level in device.capabilities
            or Capability.window_shade_level in device.capabilities
        ):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if Capability.door_control in device.capabilities:
            self._attr_device_class = CoverDeviceClass.DOOR
        elif Capability.window_shade in device.capabilities:
            self._attr_device_class = CoverDeviceClass.SHADE
        elif Capability.garage_door_control in device.capabilities:
            self._attr_device_class = CoverDeviceClass.GARAGE

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        # Same command for all 3 supported capabilities
        await self._device.close(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        # Same for all capability types
        await self._device.open(set_status=True)
        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if not self.supported_features & CoverEntityFeature.SET_POSITION:
            return
        # Do not set_status=True as device will report progress.
        if Capability.window_shade_level in self._device.capabilities:
            await self._device.set_window_shade_level(
                kwargs[ATTR_POSITION], set_status=False
            )
        else:
            await self._device.set_level(kwargs[ATTR_POSITION], set_status=False)

    async def async_update(self) -> None:
        """Update the attrs of the cover."""
        if Capability.door_control in self._device.capabilities:
            self._state = VALUE_TO_STATE.get(self._device.status.door)
        elif Capability.window_shade in self._device.capabilities:
            self._state = VALUE_TO_STATE.get(self._device.status.window_shade)
        elif Capability.garage_door_control in self._device.capabilities:
            self._state = VALUE_TO_STATE.get(self._device.status.door)

        if Capability.window_shade_level in self._device.capabilities:
            self._attr_current_cover_position = self._device.status.shade_level
        elif Capability.switch_level in self._device.capabilities:
            self._attr_current_cover_position = self._device.status.level

        self._attr_extra_state_attributes = {}
        battery = self._device.status.attributes[Attribute.battery].value
        if battery is not None:
            self._attr_extra_state_attributes[ATTR_BATTERY_LEVEL] = battery

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._state == CoverState.OPENING

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._state == CoverState.CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._state == CoverState.CLOSED:
            return True
        return None if self._state is None else False
