"""Xbox Remote support."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import Any

from pythonxbox.api.provider.smartglass import SmartglassProvider
from pythonxbox.api.provider.smartglass.models import InputKeyType, PowerState

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

PARALLEL_UPDATES = 1

MAP_COMMAND: dict[str, Callable[[SmartglassProvider], Callable]] = {
    "WakeUp": lambda x: x.wake_up,
    "TurnOff": lambda x: x.turn_off,
    "Reboot": lambda x: x.reboot,
    "Mute": lambda x: x.mute,
    "Unmute": lambda x: x.unmute,
    "Play": lambda x: x.play,
    "Pause": lambda x: x.pause,
    "Previous": lambda x: x.previous,
    "Next": lambda x: x.next,
    "GoHome": lambda x: x.go_home,
    "GoBack": lambda x: x.go_back,
    "ShowGuideTab": lambda x: x.show_guide_tab,
    "ShowGuide": lambda x: x.show_tv_guide,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox media_player from a config entry."""
    coordinator = entry.runtime_data.status

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
                if single_command in InputKeyType:
                    button = InputKeyType(single_command)
                    await self.client.smartglass.press_button(self._console.id, button)
                elif single_command in MAP_COMMAND:
                    await MAP_COMMAND[single_command](self.client.smartglass)(
                        self._console.id
                    )
                else:
                    await self.client.smartglass.insert_text(
                        self._console.id, single_command
                    )
                await asyncio.sleep(delay)
