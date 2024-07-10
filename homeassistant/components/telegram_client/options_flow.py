"""Options flow class."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow

from .const import (
    EVENT_MESSAGE_EDITED,
    EVENT_NEW_MESSAGE,
    KEY_BASE,
    OPTION_EVENTS,
    OPTION_INCOMING,
    OPTION_OUTGOING,
)
from .schemas import step_events_data_schema, step_new_message_data_schema


class TelegramClientOptionsFlow(OptionsFlow):
    """Options flow handler."""

    _events: dict[str, bool]
    _new_message: dict
    _message_edited: dict

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._events = config_entry.options.get(OPTION_EVENTS, {})
        self._new_message = config_entry.options.get(EVENT_NEW_MESSAGE, {})
        self._message_edited = config_entry.options.get(EVENT_MESSAGE_EDITED, {})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            self._events = user_input
            return await self.async_step_new_message()

        return self.async_show_form(
            step_id="init",
            data_schema=step_events_data_schema(
                self.config_entry.options.get(OPTION_EVENTS, {})
            ),
        )

    async def async_step_new_message(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage new message event options."""
        errors: dict[str, str] = {}
        if not self._events[EVENT_NEW_MESSAGE]:
            return await self.async_step_message_edited()
        if user_input is not None:
            if user_input.get(OPTION_INCOMING) or user_input.get(OPTION_OUTGOING):
                self._new_message = user_input
                return await self.async_step_message_edited()
            errors[KEY_BASE] = "You should select at least one of Incoming and Outgoing"

        return self.async_show_form(
            step_id=EVENT_NEW_MESSAGE,
            data_schema=step_new_message_data_schema(
                self.config_entry.options.get(EVENT_NEW_MESSAGE, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_message_edited(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage new message event options."""
        if not self._events[EVENT_MESSAGE_EDITED]:
            return await self.async_finish()
        if user_input is not None:
            self._message_edited = user_input
            return await self.async_finish()

        return self.async_show_form(
            step_id=EVENT_MESSAGE_EDITED,
            data_schema=step_new_message_data_schema(
                self.config_entry.options.get(EVENT_MESSAGE_EDITED, {})
                if user_input is None
                else user_input
            ),
        )

    async def async_finish(self) -> ConfigFlowResult:
        """Finish options flow."""
        data = {
            OPTION_EVENTS: self._events,
            EVENT_NEW_MESSAGE: self._new_message,
            EVENT_MESSAGE_EDITED: self._message_edited,
        }
        changed = self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=data,
        )
        if changed:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="", data=data)
