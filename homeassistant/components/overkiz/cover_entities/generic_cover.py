"""Base class for Overkiz covers, shutters, awnings, etc."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.cover import (
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)

from ..entity import OverkizEntity

ATTR_OBSTRUCTION_DETECTED = "obstruction-detected"

COMMANDS_STOP: list[OverkizCommand] = [
    OverkizCommand.STOP,
    OverkizCommand.MY,
]
COMMANDS_STOP_TILT: list[OverkizCommand] = [
    OverkizCommand.STOP,
    OverkizCommand.MY,
]
COMMANDS_OPEN: list[OverkizCommand] = [
    OverkizCommand.OPEN,
    OverkizCommand.UP,
    OverkizCommand.CYCLE,
]
COMMANDS_OPEN_TILT: list[OverkizCommand] = [OverkizCommand.OPEN_SLATS]
COMMANDS_CLOSE: list[OverkizCommand] = [
    OverkizCommand.CLOSE,
    OverkizCommand.DOWN,
    OverkizCommand.CYCLE,
]
COMMANDS_CLOSE_TILT: list[OverkizCommand] = [OverkizCommand.CLOSE_SLATS]

COMMANDS_SET_TILT_POSITION: list[OverkizCommand] = [OverkizCommand.SET_ORIENTATION]


class OverkizGenericCover(OverkizEntity, CoverEntity):
    """Representation of an Overkiz Cover."""

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.executor.select_state(
            OverkizState.CORE_SLATS_ORIENTATION, OverkizState.CORE_SLATE_ORIENTATION
        )
        if position is not None:
            return 100 - cast(int, position)

        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if command := self.executor.select_command(*COMMANDS_SET_TILT_POSITION):
            await self.executor.async_execute_command(
                command,
                100 - kwargs[ATTR_TILT_POSITION],
            )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

        state = self.executor.select_state(
            OverkizState.CORE_OPEN_CLOSED,
            OverkizState.CORE_SLATS_OPEN_CLOSED,
            OverkizState.CORE_OPEN_CLOSED_PARTIAL,
            OverkizState.CORE_OPEN_CLOSED_PEDESTRIAN,
            OverkizState.CORE_OPEN_CLOSED_UNKNOWN,
            OverkizState.MYFOX_SHUTTER_STATUS,
        )
        if state is not None:
            return state == OverkizCommandParam.CLOSED

        # Keep this condition after the previous one. Some device like the pedestrian gate, always return 50 as position.
        if self.current_cover_position is not None:
            return self.current_cover_position == 0

        if self.current_cover_tilt_position is not None:
            return self.current_cover_tilt_position == 0

        return None

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if command := self.executor.select_command(*COMMANDS_OPEN_TILT):
            await self.executor.async_execute_command(command)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if command := self.executor.select_command(*COMMANDS_CLOSE_TILT):
            await self.executor.async_execute_command(command)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if command := self.executor.select_command(*COMMANDS_STOP):
            await self.executor.async_execute_command(command)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        if command := self.executor.select_command(*COMMANDS_STOP_TILT):
            await self.executor.async_execute_command(command)

    def is_running(self, commands: list[OverkizCommand]) -> bool:
        """Return if the given commands are currently running."""
        return any(
            execution.get("device_url") == self.device.device_url
            and execution.get("command_name") in commands
            for execution in self.coordinator.executions.values()
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the device state attributes."""
        attr = super().extra_state_attributes or {}

        # Obstruction Detected attribute is used by HomeKit
        if self.executor.has_state(OverkizState.IO_PRIORITY_LOCK_LEVEL):
            return {**attr, **{ATTR_OBSTRUCTION_DETECTED: True}}

        return attr

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0

        if self.executor.has_command(*COMMANDS_OPEN_TILT):
            supported_features |= CoverEntityFeature.OPEN_TILT

            if self.executor.has_command(*COMMANDS_STOP_TILT):
                supported_features |= CoverEntityFeature.STOP_TILT

        if self.executor.has_command(*COMMANDS_CLOSE_TILT):
            supported_features |= CoverEntityFeature.CLOSE_TILT

        if self.executor.has_command(*COMMANDS_SET_TILT_POSITION):
            supported_features |= CoverEntityFeature.SET_TILT_POSITION

        return supported_features
