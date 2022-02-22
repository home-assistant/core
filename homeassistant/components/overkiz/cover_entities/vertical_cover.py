"""Support for Overkiz Vertical Covers."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizState, UIClass, UIWidget

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverDeviceClass,
)

from .generic_cover import COMMANDS_STOP, OverkizGenericCover

COMMANDS_OPEN = [OverkizCommand.OPEN, OverkizCommand.UP, OverkizCommand.CYCLE]
COMMANDS_CLOSE = [OverkizCommand.CLOSE, OverkizCommand.DOWN, OverkizCommand.CYCLE]

OVERKIZ_DEVICE_TO_DEVICE_CLASS = {
    UIClass.CURTAIN: CoverDeviceClass.CURTAIN,
    UIClass.EXTERIOR_SCREEN: CoverDeviceClass.BLIND,
    UIClass.EXTERIOR_VENETIAN_BLIND: CoverDeviceClass.BLIND,
    UIClass.GARAGE_DOOR: CoverDeviceClass.GARAGE,
    UIClass.GATE: CoverDeviceClass.GATE,
    UIWidget.MY_FOX_SECURITY_CAMERA: CoverDeviceClass.SHUTTER,
    UIClass.PERGOLA: CoverDeviceClass.AWNING,
    UIClass.ROLLER_SHUTTER: CoverDeviceClass.SHUTTER,
    UIClass.SWINGING_SHUTTER: CoverDeviceClass.SHUTTER,
    UIClass.WINDOW: CoverDeviceClass.WINDOW,
}


class VerticalCover(OverkizGenericCover):
    """Representation of an Overkiz vertical cover."""

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features: int = super().supported_features

        if self.executor.has_command(OverkizCommand.SET_CLOSURE):
            supported_features |= SUPPORT_SET_POSITION

        if self.executor.has_command(*COMMANDS_OPEN):
            supported_features |= SUPPORT_OPEN

            if self.executor.has_command(*COMMANDS_STOP):
                supported_features |= SUPPORT_STOP

        if self.executor.has_command(*COMMANDS_CLOSE):
            supported_features |= SUPPORT_CLOSE

        return supported_features

    @property
    def device_class(self) -> str:
        """Return the class of the device."""
        return cast(
            str,
            (
                OVERKIZ_DEVICE_TO_DEVICE_CLASS.get(self.device.widget)
                or OVERKIZ_DEVICE_TO_DEVICE_CLASS.get(self.device.ui_class)
                or CoverDeviceClass.BLIND
            ),
        )

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.executor.select_state(
            OverkizState.CORE_CLOSURE,
            OverkizState.CORE_CLOSURE_OR_ROCKER_POSITION,
            OverkizState.CORE_PEDESTRIAN_POSITION,
        )

        if position is None:
            return None

        return 100 - cast(int, position)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = 100 - kwargs[ATTR_POSITION]
        await self.executor.async_execute_command(OverkizCommand.SET_CLOSURE, position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if command := self.executor.select_command(*COMMANDS_OPEN):
            await self.executor.async_execute_command(command)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if command := self.executor.select_command(*COMMANDS_CLOSE):
            await self.executor.async_execute_command(command)
