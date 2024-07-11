"""Telegram client services."""

from typing import Any

from telethon import Button

from homeassistant.helpers import config_validation as cv

from .const import (
    FIELD_BUTTONS,
    FIELD_FILE,
    FIELD_INLINE_KEYBOARD,
    FIELD_KEYBOARD,
    FIELD_KEYBOARD_RESIZE,
    FIELD_KEYBOARD_SINGLE_USE,
    FIELD_TARGET_ID,
    FIELD_TARGET_USERNAME,
    KEY_ENTITY,
    SERVICE_DELETE_MESSAGES,
    SERVICE_EDIT_MESSAGE,
    SERVICE_SEND_MESSAGES,
)
from .coordinator import TelegramClientCoordinator


async def async_telegram_call(
    coordinator: TelegramClientCoordinator, service: str, **kwargs
) -> Any:
    """Process Telegram service call."""

    def inline_button(data):
        return (
            Button.inline(data)
            if isinstance(data, str)
            else Button.inline(data.get("text"), data.get("data"))
        )

    hass = coordinator.hass
    client = coordinator.client
    if keyboard := kwargs.pop(FIELD_KEYBOARD, None):
        if not isinstance(keyboard[0], list):
            keyboard = [keyboard]
        kwargs[FIELD_BUTTONS] = [
            [
                Button.text(
                    button,
                    resize=kwargs.pop(FIELD_KEYBOARD_RESIZE, None),
                    single_use=kwargs.pop(FIELD_KEYBOARD_SINGLE_USE, None),
                )
                for button in row
            ]
            for row in keyboard
        ]
    if inline_keyboard := kwargs.pop(FIELD_INLINE_KEYBOARD, None):
        if not isinstance(inline_keyboard[0], list):
            inline_keyboard = [inline_keyboard]
        kwargs[FIELD_BUTTONS] = [
            [inline_button(button) for button in row] for row in inline_keyboard
        ]
    if file := kwargs.get(FIELD_FILE):
        kwargs[FIELD_FILE] = list(map(hass.config.path, file))
    if service == SERVICE_SEND_MESSAGES:
        target_usernames = kwargs.pop(FIELD_TARGET_USERNAME, [])
        target_ids = kwargs.pop(FIELD_TARGET_ID, [])
        for target in target_usernames + target_ids:
            kwargs[KEY_ENTITY] = target
            message = await client.send_message(**kwargs)
        coordinator.last_sent_message_id.set_state(message.id)
    elif service == SERVICE_EDIT_MESSAGE:
        target_username = kwargs.pop(FIELD_TARGET_USERNAME, None)
        target_id = kwargs.pop(FIELD_TARGET_ID, None)
        kwargs[KEY_ENTITY] = target_username or target_id
        message = await client.edit_message(**kwargs)
        coordinator.last_edited_message_id.set_state(message.id)
    elif service == SERVICE_DELETE_MESSAGES:
        target_usernames = kwargs.pop(FIELD_TARGET_USERNAME, [])
        target_ids = kwargs.pop(FIELD_TARGET_ID, [])
        kwargs[KEY_ENTITY] = target_usernames + target_ids
        await client.delete_messages(**kwargs)
        message_ids = cv.ensure_list(kwargs.get("message_ids"))
        coordinator.last_deleted_message_id.set_state(message_ids[-1])
    else:
        raise NotImplementedError(
            f"Method {service} is not implemented for Telegram client."
        )
