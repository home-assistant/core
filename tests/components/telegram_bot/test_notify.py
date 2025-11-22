"""Test the telegram bot notify platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import freeze_time
from telegram import Chat, Message
from telegram.constants import ChatType, ParseMode

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant

from tests.common import async_capture_events


@freeze_time("2025-01-09T12:00:00+00:00")
async def test_send_message(
    hass: HomeAssistant,
    webhook_platform: None,
) -> None:
    """Test publishing ntfy message."""

    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.send_message",
        AsyncMock(
            return_value=Message(
                message_id=12345,
                date=datetime.now(),
                chat=Chat(id=123456, type=ChatType.PRIVATE),
            )
        ),
    ) as mock_send_message:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.testbot_mock_last_name_mock_title_12345678",
                ATTR_MESSAGE: "mock message",
                ATTR_TITLE: "mock title",
            },
            blocking=True,
            context=context,
        )
        await hass.async_block_till_done()

        mock_send_message.assert_called_once_with(
            12345678,
            "mock title\nmock message",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=None,
            disable_notification=False,
            reply_to_message_id=None,
            reply_markup=None,
            read_timeout=None,
            message_thread_id=None,
        )

    state = hass.states.get("notify.testbot_mock_last_name_mock_title_12345678")
    assert state
    assert state.state == "2025-01-09T12:00:00+00:00"

    assert len(events) == 1
    assert events[0].context == context
