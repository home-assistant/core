"""Tests for the telegram_bot component."""
from unittest.mock import patch

import pytest

from homeassistant.components.telegram_bot import (
    CONF_ALLOWED_CHAT_IDS,
    CONF_TRUSTED_NETWORKS,
    DOMAIN,
    initialize_bot,
)
from homeassistant.components.telegram_bot.polling import PollBot
from homeassistant.components.telegram_bot.webhooks import PushBot
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, CONF_URL
from homeassistant.setup import async_setup_component


@pytest.fixture
def config_webhooks():
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
def config_polling():
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
def mock_register_webhook():
    """Mock calls made by telegram_bot when (de)registering webhook."""
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
async def webhook_platform(hass, config_webhooks, mock_register_webhook):
    """Fixture for setting up the webhooks platform using appropriate config and mocks."""
    await async_setup_component(
        hass,
        DOMAIN,
        config_webhooks,
    )
    await hass.async_block_till_done()


@pytest.fixture
async def polling_platform(hass, config_polling):
    """Fixture for setting up the polliong platform using appropriate config and mocks."""
    await async_setup_component(
        hass,
        DOMAIN,
        config_polling,
    )
    await hass.async_block_till_done()


@pytest.fixture
def pushbot(hass, config_webhooks):
    """Fixture for an initialized `PushBot`."""
    platform_config = config_webhooks[DOMAIN][0]
    bot = initialize_bot(platform_config)
    pushbot = PushBot(hass, bot, platform_config)
    return pushbot


@pytest.fixture
def pollbot(hass, config_polling):
    """Fixture for an initialized `PollBot`."""
    platform_config = config_polling[DOMAIN][0]
    bot = initialize_bot(platform_config)
    pollbot = PollBot(hass, bot, platform_config)
    return pollbot
