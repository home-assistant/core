"""Tests for the telegram_bot integration."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest
from telegram import Bot, Chat, Message, User
from telegram.constants import ChatType

from homeassistant.components.telegram_bot import (
    CONF_ALLOWED_CHAT_IDS,
    CONF_TRUSTED_NETWORKS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_PLATFORM,
    CONF_URL,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def config_webhooks() -> dict[str, Any]:
    """Fixture for a webhooks platform configuration."""
    return {
        DOMAIN: [
            {
                CONF_PLATFORM: "webhooks",
                CONF_URL: "https://test",
                CONF_TRUSTED_NETWORKS: ["127.0.0.1"],
                CONF_API_KEY: "1234567890:ABC",
                CONF_ALLOWED_CHAT_IDS: [
                    # "me"
                    12345678,
                    # Some chat
                    -123456789,
                ],
            }
        ]
    }


@pytest.fixture
def config_polling() -> dict[str, Any]:
    """Fixture for a polling platform configuration."""
    return {
        DOMAIN: [
            {
                CONF_PLATFORM: "polling",
                CONF_API_KEY: "1234567890:ABC",
                CONF_ALLOWED_CHAT_IDS: [
                    # "me"
                    12345678,
                    # Some chat
                    -123456789,
                ],
            }
        ]
    }


@pytest.fixture
def mock_register_webhook() -> Generator[None]:
    """Mock calls made by telegram_bot when (de)registering webhook."""
    with (
        patch(
            "homeassistant.components.telegram_bot.webhooks.PushBot.register_webhook",
            return_value=True,
        ),
        patch(
            "homeassistant.components.telegram_bot.webhooks.PushBot.deregister_webhook",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture
def mock_external_calls() -> Generator[None]:
    """Mock calls that make calls to the live Telegram API."""
    test_user = User(123456, "Testbot", True)
    message = Message(
        message_id=12345,
        date=datetime.now(),
        chat=Chat(id=123456, type=ChatType.PRIVATE),
    )

    class BotMock(Bot):
        """Mock bot class."""

        __slots__ = ()

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize BotMock instance."""
            super().__init__(*args, **kwargs)
            self._bot_user = test_user

    with (
        patch("homeassistant.components.telegram_bot.Bot", BotMock),
        patch.object(BotMock, "get_me", return_value=test_user),
        patch.object(BotMock, "bot", test_user),
        patch.object(BotMock, "send_message", return_value=message),
        patch("telegram.ext.Updater._bootstrap"),
    ):
        yield


@pytest.fixture
def mock_generate_secret_token() -> Generator[str]:
    """Mock secret token generated for webhook."""
    mock_secret_token = "DEADBEEF12345678DEADBEEF87654321"
    with patch(
        "homeassistant.components.telegram_bot.webhooks.secrets.choice",
        side_effect=mock_secret_token,
    ):
        yield mock_secret_token


@pytest.fixture
def incorrect_secret_token():
    """Mock incorrect secret token."""
    return "AAAABBBBCCCCDDDDEEEEFFFF00009999"


@pytest.fixture
def update_message_command():
    """Fixture for mocking an incoming update of type message/command."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345678,
                "is_bot": False,
                "first_name": "Firstname",
                "username": "some_username",
                "language_code": "en",
            },
            "chat": {
                "id": -123456789,
                "title": "SomeChat",
                "type": "group",
                "all_members_are_administrators": True,
            },
            "date": 1644518189,
            "text": "/command",
            "entities": [
                {
                    "type": "bot_command",
                    "offset": 0,
                    "length": 7,
                }
            ],
        },
    }


@pytest.fixture
def update_message_text():
    """Fixture for mocking an incoming update of type message/text."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1441645532,
            "from": {
                "id": 12345678,
                "is_bot": False,
                "last_name": "Test Lastname",
                "first_name": "Test Firstname",
                "username": "Testusername",
            },
            "chat": {
                "last_name": "Test Lastname",
                "id": 1111111,
                "type": "private",
                "first_name": "Test Firstname",
                "username": "Testusername",
            },
            "text": "HELLO",
        },
    }


@pytest.fixture
def unauthorized_update_message_text(update_message_text):
    """Fixture for mocking an incoming update of type message/text that is not in our `allowed_chat_ids`."""
    update_message_text["message"]["from"]["id"] = 1234
    update_message_text["message"]["chat"]["id"] = 1234
    return update_message_text


@pytest.fixture
def update_callback_query():
    """Fixture for mocking an incoming update of type callback_query."""
    return {
        "update_id": 1,
        "callback_query": {
            "id": "4382bfdwdsb323b2d9",
            "from": {
                "id": 12345678,
                "type": "private",
                "is_bot": False,
                "last_name": "Test Lastname",
                "first_name": "Test Firstname",
                "username": "Testusername",
            },
            "chat_instance": "aaa111",
            "data": "Data from button callback",
            "inline_message_id": "1234csdbsk4839",
        },
    }


@pytest.fixture
async def webhook_platform(
    hass: HomeAssistant,
    config_webhooks: dict[str, Any],
    mock_register_webhook: None,
    mock_external_calls: None,
    mock_generate_secret_token: str,
) -> AsyncGenerator[None]:
    """Fixture for setting up the webhooks platform using appropriate config and mocks."""
    await async_setup_component(
        hass,
        DOMAIN,
        config_webhooks,
    )
    await hass.async_block_till_done()
    yield
    await hass.async_stop()


@pytest.fixture
async def polling_platform(
    hass: HomeAssistant, config_polling: dict[str, Any], mock_external_calls: None
) -> None:
    """Fixture for setting up the polling platform using appropriate config and mocks."""
    await async_setup_component(
        hass,
        DOMAIN,
        config_polling,
    )
    # Fire this event to start polling
    hass.bus.fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
