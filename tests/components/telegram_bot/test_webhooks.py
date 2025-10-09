"""Tests for webhooks."""

from ipaddress import IPv4Network
from unittest.mock import patch

from telegram.error import TimedOut

from homeassistant.components.telegram_bot.const import DOMAIN
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_set_webhooks_failed(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
    mock_register_webhook: None,
) -> None:
    """Test set webhooks failed."""
    mock_webhooks_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.telegram_bot.webhooks.secrets.choice",
            return_value="DEADBEEF12345678DEADBEEF87654321",
        ),
        patch(
            "homeassistant.components.telegram_bot.webhooks.Bot.set_webhook",
        ) as mock_set_webhook,
    ):
        mock_set_webhook.side_effect = [TimedOut("mock timeout"), False]

        await hass.config_entries.async_setup(mock_webhooks_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_stop()

        # first fail with exception, second fail with False
        assert mock_set_webhook.call_count == 2

        # SETUP_ERROR is result of ConfigEntryNotReady("Failed to register webhook with Telegram") in webhooks.py
        assert mock_webhooks_config_entry.state == ConfigEntryState.SETUP_ERROR

        # test fail after retries

        mock_set_webhook.reset_mock()
        mock_set_webhook.side_effect = TimedOut("mock timeout")

        await hass.config_entries.async_reload(mock_webhooks_config_entry.entry_id)
        await hass.async_block_till_done()

        # 3 retries
        assert mock_set_webhook.call_count == 3

        assert mock_webhooks_config_entry.state == ConfigEntryState.SETUP_ERROR
        await hass.async_block_till_done()


async def test_set_webhooks(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
    mock_register_webhook: None,
    mock_generate_secret_token,
) -> None:
    """Test set webhooks success."""
    mock_webhooks_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_webhooks_config_entry.entry_id)

    await hass.async_block_till_done()

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


async def test_webhooks_deregister_failed(
    hass: HomeAssistant,
    webhook_platform,
    mock_external_calls: None,
    mock_generate_secret_token,
) -> None:
    """Test deregister webhooks."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.telegram_bot.webhooks.Bot.delete_webhook",
    ) as mock_delete_webhook:
        mock_delete_webhook.side_effect = TimedOut("mock timeout")
        await hass.config_entries.async_unload(config_entry.entry_id)

    mock_delete_webhook.assert_called_once()
    assert config_entry.state == ConfigEntryState.NOT_LOADED
