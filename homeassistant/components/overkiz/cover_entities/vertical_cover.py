"""Support for Overkiz Vertical Covers."""
from __future__ import annotations

from typing import Any, Union, cast

from pyoverkiz.enums import OverkizCommand, OverkizState, UIClass, UIWidget

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
)

from .generic_cover import COMMANDS_STOP, OverkizGenericCover

COMMANDS_OPEN = [OverkizCommand.OPEN, OverkizCommand.UP, OverkizCommand.CYCLE]
COMMANDS_CLOSE = [OverkizCommand.CLOSE, OverkizCommand.DOWN, OverkizCommand.CYCLE]

OVERKIZ_DEVICE_TO_DEVICE_CLASS = {
    UIClass.CURTAIN: DEVICE_CLASS_CURTAIN,
    UIClass.EXTERIOR_SCREEN: DEVICE_CLASS_BLIND,
    UIClass.EXTERIOR_VENETIAN_BLIND: DEVICE_CLASS_BLIND,
    UIClass.GARAGE_DOOR: DEVICE_CLASS_GARAGE,
    UIClass.GATE: DEVICE_CLASS_GATE,
    UIWidget.MY_FOX_SECURITY_CAMERA: DEVICE_CLASS_SHUTTER,
    UIClass.PERGOLA: DEVICE_CLASS_AWNING,
    UIClass.ROLLER_SHUTTER: DEVICE_CLASS_SHUTTER,
    UIClass.SWINGING_SHUTTER: DEVICE_CLASS_SHUTTER,
    UIClass.WINDOW: DEVICE_CLASS_WINDOW,
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
                or DEVICE_CLASS_BLIND
            ),
        )

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = cast(
            Union[int, None],
            self.executor.select_state(
                OverkizState.CORE_CLOSURE,
                OverkizState.CORE_CLOSURE_OR_ROCKER_POSITION,
                OverkizState.CORE_PEDESTRIAN_POSITION,
            ),
        )

        # Uno devices can have a position not in 0 to 100 range when unknown
        if position is None or position < 0 or position > 100:
            return None

        return 100 - position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = 100 - kwargs.get(ATTR_POSITION, 0)
        await self.executor.async_execute_command(OverkizCommand.SET_CLOSURE, position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if command := self.executor.select_command(*COMMANDS_OPEN):
            await self.executor.async_execute_command(command)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if command := self.executor.select_command(*COMMANDS_CLOSE):
            await self.executor.async_execute_command(command)
