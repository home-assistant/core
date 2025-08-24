"""Remote control support for Apple TV."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from propcache.api import cached_property
from pyatv.const import InputAction, KeyboardFocusState
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    RemoteEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AppleTvConfigEntry
from .const import (
    DOMAIN,
    SERVICE_APPEND_SEARCH_TEXT,
    SERVICE_CLEAR_SEARCH_TEXT,
    SERVICE_SET_SEARCH_TEXT,
)
from .entity import AppleTVEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
COMMAND_TO_ATTRIBUTE = {
    "wakeup": ("power", "turn_on"),
    "suspend": ("power", "turn_off"),
    "turn_on": ("power", "turn_on"),
    "turn_off": ("power", "turn_off"),
    "volume_up": ("audio", "volume_up"),
    "volume_down": ("audio", "volume_down"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Apple TV remote based on a config entry."""
    platform = entity_platform.async_get_current_platform()
    # Register the services
    platform.async_register_entity_service(
        SERVICE_SET_SEARCH_TEXT,
        {vol.Required(conversation.ATTR_TEXT): cv.string},
        "async_set_search_text",
    )
    platform.async_register_entity_service(
        SERVICE_APPEND_SEARCH_TEXT,
        {vol.Required(conversation.ATTR_TEXT): cv.string},
        "async_append_search_text",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_SEARCH_TEXT,
        None,
        "async_clear_search_text",
    )

    name: str = config_entry.data[CONF_NAME]
    # apple_tv config entries always have a unique id
    assert config_entry.unique_id is not None
    manager = config_entry.runtime_data
    async_add_entities([AppleTVRemote(name, config_entry.unique_id, manager)])


class AppleTVRemote(AppleTVEntity, RemoteEntity):
    """Device that sends commands to an Apple TV."""

    @cached_property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self.atv is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.manager.connect()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.manager.disconnect()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS)

        if not self.atv:
            _LOGGER.error("Unable to send commands, not connected to %s", self.name)
            return

        for _ in range(num_repeats):
            for single_command in command:
                attr_value: Any = None
                if attributes := COMMAND_TO_ATTRIBUTE.get(single_command):
                    attr_value = self.atv
                    for attr_name in attributes:
                        attr_value = getattr(attr_value, attr_name, None)
                if not attr_value:
                    attr_value = getattr(self.atv.remote_control, single_command, None)
                if not attr_value:
                    raise ValueError("Command not found. Exiting sequence")

                _LOGGER.debug("Sending command %s", single_command)

                if hold_secs >= 1:
                    await attr_value(action=InputAction.Hold)
                else:
                    await attr_value()

                await asyncio.sleep(delay)

    def ok_to_change_text(self) -> bool:
        """Check the status of the keyboard."""
        if not self.atv:
            _LOGGER.error("Unable to set text, not connected to Apple TV")
            return False

        if not self.atv.keyboard:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="keyboard_not_supported"
            )

        if self.atv.keyboard.text_focus_state != KeyboardFocusState.Focused:
            _LOGGER.error("Keyboard not focused on Apple TV")
            return False

        return True

    async def async_set_search_text(self, text: str) -> None:
        """Set the search text on the Apple TV."""
        if not self.ok_to_change_text():
            return

        assert self.atv is not None
        _LOGGER.debug("Setting search text to '%s'", text)
        await self.atv.keyboard.text_set(text)

    async def async_append_search_text(self, text: str) -> None:
        """Append text to the current search text on the Apple TV."""
        if not self.ok_to_change_text():
            return

        assert self.atv is not None
        _LOGGER.debug("Appending search text '%s'", text)
        await self.atv.keyboard.text_append(text)

    async def async_clear_search_text(self) -> None:
        """Clear the current search text on the Apple TV."""
        if not self.ok_to_change_text():
            return

        assert self.atv is not None
        _LOGGER.debug("Clearing search text")
        await self.atv.keyboard.text_clear()
