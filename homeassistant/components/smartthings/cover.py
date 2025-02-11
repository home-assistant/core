"""Support for covers through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings.models import Attribute, Capability, Command

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry, SmartThingsDeviceCoordinator
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add covers for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsCover(device, capability)
        for device in devices
        for capability in device.data
        if capability in CAPABILITIES
    )


# def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
#     """Return all capabilities supported if minimum required are present."""
#     min_required = [
#         Capability.door_control,
#         Capability.garage_door_control,
#         Capability.window_shade,
#     ]
#     # Must have one of the min_required
#     if any(capability in capabilities for capability in min_required):
#         # Return all capabilities supported/consumed
#         return [
#             *min_required,
#             Capability.battery,
#             Capability.switch_level,
#             Capability.window_shade_level,
#         ]
#
#     return None


class SmartThingsCover(SmartThingsEntity, CoverEntity):
    """Define a SmartThings cover."""

    _state: CoverState | None = None

    def __init__(
        self, device: SmartThingsDeviceCoordinator, capability: Capability
    ) -> None:
        """Initialize the cover class."""
        super().__init__(device)
        self.capability = capability
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
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
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id, self.capability, Command.CLOSE
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id, self.capability, Command.OPEN
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            self.capability,
            (
                Command.SET_SHADE_LEVEL
                if self.capability is Capability.WINDOW_SHADE_LEVEL
                else Command.SET_LEVEL
            ),
            argument=kwargs[ATTR_POSITION],
        )

    def _update_attr(self) -> None:
        """Update the attrs of the cover."""
        attribute = {
            Capability.WINDOW_SHADE: Attribute.WINDOW_SHADE,
            Capability.DOOR_CONTROL: Attribute.DOOR,
        }.get(self.capability)
        self._state = VALUE_TO_STATE.get(
            self.get_attribute_value(self.capability, attribute)
        )

        if self.supports_capability(Capability.SWITCH_LEVEL):
            self._attr_current_cover_position = self.get_attribute_value(
                Capability.SWITCH_LEVEL, Attribute.LEVEL
            )

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
