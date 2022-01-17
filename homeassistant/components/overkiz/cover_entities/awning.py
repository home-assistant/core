"""Support for Overkiz awnings."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizState

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_AWNING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
)

from .generic_cover import COMMANDS_STOP, OverkizGenericCover


class Awning(OverkizGenericCover):
    """Representation of an Overkiz awning."""

    _attr_device_class = DEVICE_CLASS_AWNING

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features: int = super().supported_features

        if self.executor.has_command(OverkizCommand.SET_DEPLOYMENT):
            supported_features |= SUPPORT_SET_POSITION

        if self.executor.has_command(OverkizCommand.DEPLOY):
            supported_features |= SUPPORT_OPEN

            if self.executor.has_command(*COMMANDS_STOP):
                supported_features |= SUPPORT_STOP

        if self.executor.has_command(OverkizCommand.UNDEPLOY):
            supported_features |= SUPPORT_CLOSE

        return supported_features

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if current_position := self.executor.select_state(OverkizState.CORE_DEPLOYMENT):
            return cast(int, current_position)

        return None

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION, 0)
        await self.executor.async_execute_command(
            OverkizCommand.SET_DEPLOYMENT, position
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.executor.async_execute_command(OverkizCommand.DEPLOY)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.executor.async_execute_command(OverkizCommand.UNDEPLOY)
