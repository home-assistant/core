"""Buttons for Immich Frames."""

from collections.abc import Awaitable, Callable
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator
from .entity import ImmichFramesEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichFramesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up frame controls."""
    coordinator = entry.runtime_data
    async_add_entities(
        FrameButton(coordinator, key, action)
        for key, action in (
            ("next", coordinator.async_next),
            ("previous", coordinator.async_previous),
            ("refresh", coordinator.async_refresh_now),
            ("clear_cache", coordinator.async_clear_cache),
        )
    )


class FrameButton(ImmichFramesEntity, ButtonEntity):
    """A frame navigation or maintenance button."""

    def __init__(
        self,
        coordinator: ImmichFramesDataUpdateCoordinator,
        key: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, key)
        self._action = action

    @override
    async def async_press(self) -> None:
        """Run the selected frame action."""
        await self._action()
