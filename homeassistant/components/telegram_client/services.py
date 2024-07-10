"""Telegram client services."""

from typing import Any

from telethon import Button

from .const import (
    FIELD_BUTTONS,
    FIELD_FILE,
    FIELD_INLINE_KEYBOARD,
    FIELD_KEYBOARD,
    FIELD_KEYBOARD_RESIZE,
    FIELD_KEYBOARD_SINGLE_USE,
    FIELD_TARGET_ID,
    FIELD_TARGET_USERNAME,
    SERVICE_EDIT_MESSAGE,
    SERVICE_SEND_MESSAGE,
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
    if service == SERVICE_SEND_MESSAGE:
        target_usernames = kwargs.pop(FIELD_TARGET_USERNAME, [])
        if not isinstance(target_usernames, list):
            target_usernames = [target_usernames]
        target_ids = kwargs.pop(FIELD_TARGET_ID, [])
        if not isinstance(target_ids, list):
            target_ids = [target_ids]
        for target in target_usernames + target_ids:
            kwargs["entity"] = target
            message = await client.send_message(**kwargs)
        if isinstance(message, list):
            message = message.pop()
        coordinator.last_sent_message_id.set_state(message.id)
        return message
    if service == SERVICE_EDIT_MESSAGE:
        kwargs["entity"] = kwargs.pop(
            FIELD_TARGET_USERNAME, kwargs.pop(FIELD_TARGET_ID, None)
        )
        message = await client.edit_message(**kwargs)
        coordinator.last_edited_message_id.set_state(message.id)
        return message
    raise NotImplementedError(
        f"Method {service} is not implemented for Telegram client."
    )
