"""Xbox Remote support."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from xbox.webapi.api.provider.smartglass.models import InputKeyType, PowerState

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XboxConfigEntry
from .entity import XboxConsoleBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox media_player from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [XboxRemote(console, coordinator) for console in coordinator.consoles.result]
    )


class XboxRemote(XboxConsoleBaseEntity, RemoteEntity):
    """Representation of an Xbox remote."""

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.data.status.power_state == PowerState.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Xbox on."""
        await self.client.smartglass.wake_up(self._console.id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Xbox off."""
        await self.client.smartglass.turn_off(self._console.id)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send controller or text input to the Xbox."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                try:
                    button = InputKeyType(single_command)
                    await self.client.smartglass.press_button(self._console.id, button)
                except ValueError:
                    await self.client.smartglass.insert_text(
                        self._console.id, single_command
                    )
                await asyncio.sleep(delay)
