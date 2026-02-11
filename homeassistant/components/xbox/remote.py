"""Xbox Remote support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from functools import wraps
from http import HTTPStatus
import logging
from typing import Any, Concatenate

from httpx import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.provider.smartglass import SmartglassProvider
from pythonxbox.api.provider.smartglass.models import InputKeyType, PowerState

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import XboxConfigEntry
from .entity import XboxConsoleBaseEntity

_LOGGER = logging.getLogger(__name__)

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
    devices_added: set[str] = set()

    coordinator = entry.runtime_data.status
    consoles = entry.runtime_data.consoles

    @callback
    def add_entities() -> None:
        nonlocal devices_added

        new_devices = set(consoles.data) - devices_added

        if new_devices:
            async_add_entities(
                [
                    XboxRemote(consoles.data[console_id], coordinator)
                    for console_id in new_devices
                ]
            )

            devices_added |= new_devices
        devices_added &= set(consoles.data)

    entry.async_on_unload(consoles.async_add_listener(add_entities))
    add_entities()


def exception_handler[**_P, _R](
    func: Callable[Concatenate[XboxRemote, _P], Awaitable[_R]],
) -> Callable[Concatenate[XboxRemote, _P], Coroutine[Any, Any, _R]]:
    """Catch Xbox errors."""

    @wraps(func)
    async def wrapper(
        self: XboxRemote,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        """Catch Xbox errors and raise HomeAssistantError."""
        try:
            return await func(self, *args, **kwargs)
        except TimeoutException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

    return wrapper


class XboxRemote(XboxConsoleBaseEntity, RemoteEntity):
    """Representation of an Xbox remote."""

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.data.status.power_state == PowerState.On

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Xbox on."""
        try:
            await self.client.smartglass.wake_up(self._console.id)
        except HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="turn_on_failed",
                ) from e
            raise

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Xbox off."""
        await self.client.smartglass.turn_off(self._console.id)

    @exception_handler
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
