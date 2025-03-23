"""Support for covers through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

VALUE_TO_STATE = {
    "closed": CoverState.CLOSED,
    "closing": CoverState.CLOSING,
    "open": CoverState.OPEN,
    "opening": CoverState.OPENING,
    "partially open": CoverState.OPEN,
    "unknown": None,
}

CAPABILITIES = (Capability.WINDOW_SHADE, Capability.DOOR_CONTROL)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add covers for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsCover(entry_data.client, device, Capability(capability))
        for device in entry_data.devices.values()
        for capability in device.status[MAIN]
        if capability in CAPABILITIES
    )


class SmartThingsCover(SmartThingsEntity, CoverEntity):
    """Define a SmartThings cover."""

    _attr_name = None
    _state: CoverState | None = None

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        capability: Capability,
    ) -> None:
        """Initialize the cover class."""
        super().__init__(
            client,
            device,
            {
                capability,
                Capability.BATTERY,
                Capability.WINDOW_SHADE_LEVEL,
                Capability.SWITCH_LEVEL,
            },
        )
        self.capability = capability
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if self.supports_capability(Capability.WINDOW_SHADE_LEVEL):
            self.level_capability = Capability.WINDOW_SHADE_LEVEL
            self.level_command = Command.SET_SHADE_LEVEL
        else:
            self.level_capability = Capability.SWITCH_LEVEL
            self.level_command = Command.SET_LEVEL
        if self.supports_capability(
            Capability.SWITCH_LEVEL
        ) or self.supports_capability(Capability.WINDOW_SHADE_LEVEL):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if self.supports_capability(Capability.DOOR_CONTROL):
            self._attr_device_class = CoverDeviceClass.DOOR
        elif self.supports_capability(Capability.WINDOW_SHADE):
            self._attr_device_class = CoverDeviceClass.SHADE

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.execute_device_command(self.capability, Command.CLOSE)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.execute_device_command(self.capability, Command.OPEN)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.execute_device_command(
            self.level_capability,
            self.level_command,
            argument=kwargs[ATTR_POSITION],
        )

    def _update_attr(self) -> None:
        """Update the attrs of the cover."""
        attribute = {
            Capability.WINDOW_SHADE: Attribute.WINDOW_SHADE,
            Capability.DOOR_CONTROL: Attribute.DOOR,
        }[self.capability]
        self._state = VALUE_TO_STATE.get(
            self.get_attribute_value(self.capability, attribute)
        )

        if self.supports_capability(Capability.SWITCH_LEVEL):
            self._attr_current_cover_position = self.get_attribute_value(
                Capability.SWITCH_LEVEL, Attribute.LEVEL
            )
        elif self.supports_capability(Capability.WINDOW_SHADE_LEVEL):
            self._attr_current_cover_position = self.get_attribute_value(
                Capability.WINDOW_SHADE_LEVEL, Attribute.SHADE_LEVEL
            )

        # Deprecated, remove in 2025.10
        self._attr_extra_state_attributes = {}
        if self.supports_capability(Capability.BATTERY):
            self._attr_extra_state_attributes[ATTR_BATTERY_LEVEL] = (
                self.get_attribute_value(Capability.BATTERY, Attribute.BATTERY)
            )

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
