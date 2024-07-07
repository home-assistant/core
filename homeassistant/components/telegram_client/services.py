"""Telegram client services."""

from homeassistant.core import ServiceCall

from .const import (
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_MESSAGE,
    ATTR_PARSER,
    ATTR_REPLY_TO_MSGID,
    ATTR_SCHEDULE,
    ATTR_TARGET_ID,
    ATTR_TARGET_USERNAME,
    SERVICE_SEND_MESSAGE,
)
from .coordinator import TelegramClientCoordinator


async def async_telegram_call(
    coordinator: TelegramClientCoordinator, call: ServiceCall
) -> None:
    """Process Telegram service call."""
    service = call.service
    target = call.data.get(ATTR_TARGET_USERNAME) or call.data.get(ATTR_TARGET_ID)
    reply_to = call.data.get(ATTR_REPLY_TO_MSGID)
    parse_mode = call.data.get(ATTR_PARSER)
    link_preview = not call.data.get(ATTR_DISABLE_WEB_PREV, False)
    silent = call.data.get(ATTR_DISABLE_NOTIF)
    schedule = call.data.get(ATTR_SCHEDULE)
    client = coordinator.client

    if service == SERVICE_SEND_MESSAGE:
        message = call.data[ATTR_MESSAGE]
        await coordinator.async_client_call(
            client.send_message(
                target,
                message,
                reply_to=reply_to,
                parse_mode=parse_mode,
                link_preview=link_preview,
                silent=silent,
                schedule=schedule,
            )
        )
