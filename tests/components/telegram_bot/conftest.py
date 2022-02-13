"""Tests for the telegram_bot component."""
from unittest.mock import patch, Mock

import pytest
from telegram import Update

from homeassistant import config as hass_config, config_entries
from homeassistant.core import HomeAssistant, callback
import homeassistant.components.notify as notify
from homeassistant.components.telegram_bot import (
    DOMAIN,
    SERVICE_SEND_MESSAGE,
    CONF_TRUSTED_NETWORKS,
    initialize_bot,
)
from homeassistant.components.telegram_bot.polling import PollBot
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL, PushBot
from homeassistant.const import (
    SERVICE_RELOAD,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_PLATFORM,
    CONF_API_KEY,
)
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path, MockConfigEntry, async_mock_service


@pytest.fixture
def config_webhooks():
    return {
        DOMAIN: [
            {
                CONF_PLATFORM: "webhooks",
                CONF_URL: "https://test",
                CONF_TRUSTED_NETWORKS: ["127.0.0.1"],
                CONF_API_KEY: "1234567890:ABC",
                "allowed_chat_ids": [
                    # "me"
                    12345678,
                    # Some chat
                    -123456789,
                ],
            }
        ]
    }


@pytest.fixture
def config_polling():
    return {
        DOMAIN: [
            {
                CONF_PLATFORM: "polling",
                CONF_API_KEY: "1234567890:ABC",
                "allowed_chat_ids": [
                    # "me"
                    12345678,
                    # Some chat
                    -123456789,
                ],
            }
        ]
    }


@pytest.fixture
def mock_register_webhook():
    with patch(
        "homeassistant.components.telegram_bot.webhooks.PushBot.register_webhook",
        return_value=True,
    ), patch(
        "homeassistant.components.telegram_bot.webhooks.PushBot.deregister_webhook",
        return_value=True,
    ):
        yield


@pytest.fixture
def update_message_command():
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
def update_callback_query():
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
async def webhook_platform(hass, config_webhooks, mock_register_webhook):
    await async_setup_component(
        hass,
        DOMAIN,
        config_webhooks,
    )
    await hass.async_block_till_done()


@pytest.fixture
async def polling_platform(hass, config_polling):
    await async_setup_component(
        hass,
        DOMAIN,
        config_polling,
    )
    await hass.async_block_till_done()


@pytest.fixture
def pushbot(hass, config_webhooks):
    platform_config = config_webhooks[DOMAIN][0]
    bot = initialize_bot(platform_config)
    pushbot = PushBot(hass, bot, platform_config)
    return pushbot


@pytest.fixture
def pollbot(hass, config_polling):
    platform_config = config_polling[DOMAIN][0]
    bot = initialize_bot(platform_config)
    pollbot = PollBot(hass, bot, platform_config)
    return pollbot
