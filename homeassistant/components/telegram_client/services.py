"""Telegram client services."""

from typing import Any

from telethon import Button

from .const import (
    ATTR_BUTTONS,
    ATTR_FILE,
    ATTR_INLINE_KEYBOARD,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_RESIZE,
    ATTR_KEYBOARD_SINGLE_USE,
    ATTR_TARGET_ID,
    ATTR_TARGET_USERNAME,
    CONF_LAST_SENT_MESSAGE_ID,
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
    kwargs["entity"] = kwargs.pop(
        ATTR_TARGET_USERNAME, kwargs.pop(ATTR_TARGET_ID, None)
    )
    if keyboard := kwargs.pop(ATTR_KEYBOARD, None):
        if not isinstance(keyboard[0], list):
            keyboard = [keyboard]
        kwargs[ATTR_BUTTONS] = [
            [
                Button.text(
                    button,
                    resize=kwargs.pop(ATTR_KEYBOARD_RESIZE, None),
                    single_use=kwargs.pop(ATTR_KEYBOARD_SINGLE_USE, None),
                )
                for button in row
            ]
            for row in keyboard
        ]
    if inline_keyboard := kwargs.pop(ATTR_INLINE_KEYBOARD, None):
        if not isinstance(inline_keyboard[0], list):
            inline_keyboard = [inline_keyboard]
        kwargs[ATTR_BUTTONS] = [
            [inline_button(button) for button in row] for row in inline_keyboard
        ]
    if file := kwargs.get(ATTR_FILE):
        kwargs[ATTR_FILE] = list(map(hass.config.path, file))
    if service == SERVICE_SEND_MESSAGE:
        message = await client.send_message(**kwargs)
        if isinstance(message, list):
            message = message.pop()
        coordinator.data.update({CONF_LAST_SENT_MESSAGE_ID: message.id})
        coordinator.async_update_listeners()
        return message
    raise NotImplementedError(
        f"Method {service} is not implemented for Telegram client."
    )
