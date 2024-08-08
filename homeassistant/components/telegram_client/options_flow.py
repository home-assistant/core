"""Telegram client entry options flow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow

from .const import (
    EVENT_CALLBACK_QUERY,
    EVENT_CHAT_ACTION,
    EVENT_INLINE_QUERY,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGE_EDITED,
    EVENT_MESSAGE_READ,
    EVENT_NEW_MESSAGE,
    EVENT_USER_UPDATE,
    KEY_BASE,
    OPTION_EVENTS,
    OPTION_FORWARDS,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    STRING_FORWARDS_ONLY_FORWARDS,
)
from .schemas import (
    step_callback_query_data_schema,
    step_chat_action_data_schema,
    step_events_data_schema,
    step_inline_query_data_schema,
    step_message_deleted_data_schema,
    step_message_edited_data_schema,
    step_message_read_data_schema,
    step_new_message_data_schema,
    step_user_update_data_schema,
)


class TelegramClientOptionsFlow(OptionsFlow):
    """Telegram client entry options flow."""

    _events_options: dict[str, bool]
    _new_message_options: dict[str, str | bool]
    _message_edited_options: dict[str, str | bool]
    _message_read_options: dict[str, str | bool]
    _message_deleted_options: dict[str, str | bool]
    _callback_query_options: dict[str, str | bool]
    _inline_query_options: dict[str, str | bool]
    _chat_action_options: dict[str, str | bool]
    _user_update_options: dict[str, str | bool]

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Handle Telegram client entry options flow initialization."""
        self.config_entry = config_entry
        self._events_options = config_entry.options.get(OPTION_EVENTS, {})
        self._new_message_options = config_entry.options.get(EVENT_NEW_MESSAGE, {})
        self._message_edited_options = config_entry.options.get(
            EVENT_MESSAGE_EDITED, {}
        )
        self._message_read_options = config_entry.options.get(EVENT_MESSAGE_READ, {})
        self._message_deleted_options = config_entry.options.get(
            EVENT_MESSAGE_DELETED, {}
        )
        self._callback_query_options = config_entry.options.get(
            EVENT_CALLBACK_QUERY, {}
        )
        self._inline_query_options = config_entry.options.get(EVENT_INLINE_QUERY, {})
        self._chat_action_options = config_entry.options.get(EVENT_CHAT_ACTION, {})
        self._user_update_options = config_entry.options.get(EVENT_USER_UPDATE, {})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of events to listen step."""
        if user_input is not None:
            self._events_options = user_input
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
        """Handle input of new message event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_NEW_MESSAGE):
            return await self.async_step_message_edited()
        if user_input is not None:
            if (
                not user_input.get(OPTION_INCOMING)
                and not user_input.get(OPTION_OUTGOING)
                and not user_input.get(OPTION_FORWARDS)
            ):
                errors[KEY_BASE] = (
                    "You should select at least one of 'Incoming' and 'Outgoing'"
                )
            if user_input.get(OPTION_FORWARDS) and (
                user_input.get(OPTION_INCOMING) or user_input.get(OPTION_OUTGOING)
            ):
                errors[OPTION_FORWARDS] = (
                    f"You can't select Forwards='{STRING_FORWARDS_ONLY_FORWARDS}' if you selected 'Incoming' or 'Outgoing'"
                )
            if not errors:
                self._new_message_options = user_input
                return await self.async_step_message_edited()

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
        """Handle input of message edited event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_MESSAGE_EDITED):
            return await self.async_step_message_read()
        if user_input is not None:
            if (
                not user_input.get(OPTION_INCOMING)
                and not user_input.get(OPTION_OUTGOING)
                and not user_input.get(OPTION_FORWARDS)
            ):
                errors[KEY_BASE] = (
                    "You should select at least one of 'Incoming' and 'Outgoing'"
                )
            if user_input.get(OPTION_FORWARDS) and (
                user_input.get(OPTION_INCOMING) or user_input.get(OPTION_OUTGOING)
            ):
                errors[OPTION_FORWARDS] = (
                    f"You can't select Forwards='{STRING_FORWARDS_ONLY_FORWARDS}' if you selected 'Incoming' or 'Outgoing'"
                )
            if not errors:
                self._message_edited_options = user_input
                return await self.async_step_message_read()

        return self.async_show_form(
            step_id=EVENT_MESSAGE_EDITED,
            data_schema=step_message_edited_data_schema(
                self.config_entry.options.get(EVENT_MESSAGE_EDITED, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_message_read(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of message read event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_MESSAGE_READ):
            return await self.async_step_message_deleted()
        if user_input is not None:
            self._message_read_options = user_input
            return await self.async_step_message_deleted()

        return self.async_show_form(
            step_id=EVENT_MESSAGE_READ,
            data_schema=step_message_read_data_schema(
                self.config_entry.options.get(EVENT_MESSAGE_READ, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_message_deleted(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of message deleted event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_MESSAGE_DELETED):
            return await self.async_step_callback_query()
        if user_input is not None:
            self._message_deleted_options = user_input
            return await self.async_step_callback_query()

        return self.async_show_form(
            step_id=EVENT_MESSAGE_DELETED,
            data_schema=step_message_deleted_data_schema(
                self.config_entry.options.get(EVENT_MESSAGE_DELETED, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_callback_query(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of callback query event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_CALLBACK_QUERY):
            return await self.async_step_inline_query()
        if user_input is not None:
            self._callback_query_options = user_input
            return await self.async_step_inline_query()

        return self.async_show_form(
            step_id=EVENT_CALLBACK_QUERY,
            data_schema=step_callback_query_data_schema(
                self.config_entry.options.get(EVENT_CALLBACK_QUERY, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_inline_query(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of inline query event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_INLINE_QUERY):
            return await self.async_step_chat_action()
        if user_input is not None:
            self._inline_query_options = user_input
            return await self.async_step_chat_action()

        return self.async_show_form(
            step_id=EVENT_INLINE_QUERY,
            data_schema=step_inline_query_data_schema(
                self.config_entry.options.get(EVENT_INLINE_QUERY, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_chat_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of chat action event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_CHAT_ACTION):
            return await self.async_step_user_update()
        if user_input is not None:
            self._chat_action_options = user_input
            return await self.async_step_user_update()

        return self.async_show_form(
            step_id=EVENT_CHAT_ACTION,
            data_schema=step_chat_action_data_schema(
                self.config_entry.options.get(EVENT_CHAT_ACTION, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_step_user_update(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of user update event parameters step."""
        errors: dict[str, str] = {}
        if not self._events_options.get(EVENT_USER_UPDATE):
            return await self.async_finish()
        if user_input is not None:
            self._user_update_options = user_input
            return await self.async_finish()

        return self.async_show_form(
            step_id=EVENT_USER_UPDATE,
            data_schema=step_user_update_data_schema(
                self.config_entry.options.get(EVENT_USER_UPDATE, {})
                if user_input is None
                else user_input
            ),
            errors=errors,
        )

    async def async_finish(self) -> ConfigFlowResult:
        """Handle Telegram client entry options creation."""
        return self.async_create_entry(
            title="",
            data={
                OPTION_EVENTS: self._events_options,
                EVENT_NEW_MESSAGE: self._new_message_options,
                EVENT_MESSAGE_EDITED: self._message_edited_options,
                EVENT_MESSAGE_READ: self._message_read_options,
                EVENT_MESSAGE_DELETED: self._message_deleted_options,
                EVENT_CALLBACK_QUERY: self._callback_query_options,
                EVENT_INLINE_QUERY: self._inline_query_options,
                EVENT_CHAT_ACTION: self._chat_action_options,
                EVENT_USER_UPDATE: self._user_update_options,
            },
        )
