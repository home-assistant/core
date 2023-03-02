"""Support for Overkiz Vertical Covers."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import (
    OverkizCommand,
    OverkizCommandParam,
    OverkizState,
    UIClass,
    UIWidget,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntityFeature,
)

from ..coordinator import OverkizDataUpdateCoordinator
from .generic_cover import (
    COMMANDS_CLOSE_TILT,
    COMMANDS_OPEN_TILT,
    COMMANDS_STOP,
    OverkizGenericCover,
)

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
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = super().supported_features

        if self.executor.has_command(OverkizCommand.SET_CLOSURE):
            supported_features |= CoverEntityFeature.SET_POSITION

        if self.executor.has_command(*COMMANDS_OPEN):
            supported_features |= CoverEntityFeature.OPEN

            if self.executor.has_command(*COMMANDS_STOP):
                supported_features |= CoverEntityFeature.STOP

        if self.executor.has_command(*COMMANDS_CLOSE):
            supported_features |= CoverEntityFeature.CLOSE

        return supported_features

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the class of the device."""
        return (
            OVERKIZ_DEVICE_TO_DEVICE_CLASS.get(self.device.widget)
            or OVERKIZ_DEVICE_TO_DEVICE_CLASS.get(self.device.ui_class)
            or CoverDeviceClass.BLIND
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

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

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        if self.is_running(COMMANDS_OPEN + COMMANDS_OPEN_TILT):
            return True

        # Check if cover is moving based on current state
        is_moving = self.device.states.get(OverkizState.CORE_MOVING)
        current_closure = self.device.states.get(OverkizState.CORE_CLOSURE)
        target_closure = self.device.states.get(OverkizState.CORE_TARGET_CLOSURE)

        if not is_moving or not current_closure or not target_closure:
            return None

        return cast(int, current_closure.value) > cast(int, target_closure.value)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        if self.is_running(COMMANDS_CLOSE + COMMANDS_CLOSE_TILT):
            return True

        # Check if cover is moving based on current state
        is_moving = self.device.states.get(OverkizState.CORE_MOVING)
        current_closure = self.device.states.get(OverkizState.CORE_CLOSURE)
        target_closure = self.device.states.get(OverkizState.CORE_TARGET_CLOSURE)

        if not is_moving or not current_closure or not target_closure:
            return None

        return cast(int, current_closure.value) < cast(int, target_closure.value)


class LowSpeedCover(VerticalCover):
    """Representation of an Overkiz Low Speed cover."""

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator)
        self._attr_name = "Low speed"
        self._attr_unique_id = f"{self._attr_unique_id}_low_speed"

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.async_set_cover_position_low_speed(**kwargs)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_set_cover_position_low_speed(**{ATTR_POSITION: 100})

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_set_cover_position_low_speed(**{ATTR_POSITION: 0})

    async def async_set_cover_position_low_speed(self, **kwargs: Any) -> None:
        """Move the cover to a specific position with a low speed."""
        position = 100 - kwargs.get(ATTR_POSITION, 0)

        await self.executor.async_execute_command(
            OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED,
            position,
            OverkizCommandParam.LOWSPEED,
        )
