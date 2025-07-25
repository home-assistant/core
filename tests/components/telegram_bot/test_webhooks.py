"""Tests for webhooks."""

from datetime import datetime
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, patch

from telegram import WebhookInfo
from telegram.error import TimedOut

from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_set_webhooks_failed(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
    mock_generate_secret_token,
) -> None:
    """Test set webhooks failed."""
    mock_webhooks_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.telegram_bot.webhooks.Bot.get_webhook_info",
            AsyncMock(
                return_value=WebhookInfo(
                    url="mock url",
                    last_error_date=datetime.now(),
                    has_custom_certificate=False,
                    pending_update_count=0,
                )
            ),
        ) as mock_webhook_info,
        patch(
            "homeassistant.components.telegram_bot.webhooks.Bot.set_webhook",
        ) as mock_set_webhook,
        patch(
            "homeassistant.components.telegram_bot.webhooks.ApplicationBuilder"
        ) as application_builder_class,
    ):
        mock_set_webhook.side_effect = [TimedOut("mock timeout"), False]
        application = application_builder_class.return_value.bot.return_value.updater.return_value.build.return_value
        application.initialize = AsyncMock()
        application.start = AsyncMock()

        await hass.config_entries.async_setup(mock_webhooks_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_stop()

        mock_webhook_info.assert_called_once()
        application.initialize.assert_called_once()
        application.start.assert_called_once()
        assert mock_set_webhook.call_count > 0

        # SETUP_ERROR is result of ConfigEntryNotReady("Failed to register webhook with Telegram") in webhooks.py
        assert mock_webhooks_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_set_webhooks(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
    mock_generate_secret_token,
) -> None:
    """Test set webhooks success."""
    mock_webhooks_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.telegram_bot.webhooks.Bot.get_webhook_info",
            AsyncMock(
                return_value=WebhookInfo(
                    url="mock url",
                    last_error_date=datetime.now(),
                    has_custom_certificate=False,
                    pending_update_count=0,
                )
            ),
        ) as mock_webhook_info,
        patch(
            "homeassistant.components.telegram_bot.webhooks.Bot.set_webhook",
            AsyncMock(return_value=True),
        ) as mock_set_webhook,
        patch(
            "homeassistant.components.telegram_bot.webhooks.ApplicationBuilder"
        ) as application_builder_class,
    ):
        application = application_builder_class.return_value.bot.return_value.updater.return_value.build.return_value
        application.initialize = AsyncMock()
        application.start = AsyncMock()

        await hass.config_entries.async_setup(mock_webhooks_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_stop()

        mock_webhook_info.assert_called_once()
        application.initialize.assert_called_once()
        application.start.assert_called_once()
        mock_set_webhook.assert_called_once()

        assert mock_webhooks_config_entry.state == ConfigEntryState.LOADED


async def test_webhooks_update_invalid_json(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    mock_generate_secret_token,
) -> None:
    """Test update with invalid json."""
    client = await hass_client()

    response = await client.post(
        f"{TELEGRAM_WEBHOOK_URL}_123456",
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 400

    await hass.async_block_till_done()


async def test_webhooks_unauthorized_network(
    hass: HomeAssistant,
    webhook_platform,
    mock_external_calls: None,
    mock_generate_secret_token,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test update with request outside of trusted networks."""

    client = await hass_client()

    with patch(
        "homeassistant.components.telegram_bot.webhooks.ip_address",
        return_value=IPv4Network("1.2.3.4"),
    ) as mock_remote:
        response = await client.post(
            f"{TELEGRAM_WEBHOOK_URL}_123456",
            json="mock json",
            headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
        )
        assert response.status == 401

        await hass.async_block_till_done()
        mock_remote.assert_called_once()
