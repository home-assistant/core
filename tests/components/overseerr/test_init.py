"""Tests for the Overseerr integration."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from python_overseerr.models import WebhookNotificationOptions
from syrupy import SnapshotAssertion

from homeassistant.components.overseerr import JSON_PAYLOAD, REGISTERED_NOTIFICATIONS
from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_proper_webhook_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_overseerr_client: AsyncMock,
) -> None:
    """Test the webhook configuration."""
    await setup_integration(hass, mock_config_entry)

    assert REGISTERED_NOTIFICATIONS == 222

    mock_overseerr_client.test_webhook_notification_config.assert_not_called()
    mock_overseerr_client.set_webhook_notification_config.assert_not_called()


@pytest.mark.parametrize(
    "update_mock",
    [
        {"return_value.enabled": False},
        {"return_value.types": 4},
        {"return_value.types": 4062},
        {
            "return_value.options": WebhookNotificationOptions(
                webhook_url="http://example.com", json_payload=JSON_PAYLOAD
            )
        },
        {
            "return_value.options": WebhookNotificationOptions(
                webhook_url="http://10.10.10.10:8123/api/webhook/test-webhook-id",
                json_payload='"{\\"message\\": \\"{{title}}\\"}"',
            )
        },
    ],
    ids=[
        "Disabled",
        "Smaller scope",
        "Bigger scope",
        "Webhook URL",
        "JSON Payload",
    ],
)
async def test_webhook_configuration_need_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_overseerr_client: AsyncMock,
    update_mock: dict[str, Any],
) -> None:
    """Test the webhook configuration."""
    mock_overseerr_client.get_webhook_notification_config.configure_mock(**update_mock)

    await setup_integration(hass, mock_config_entry)

    mock_overseerr_client.test_webhook_notification_config.assert_called_once()
    mock_overseerr_client.set_webhook_notification_config.assert_called_once()


@pytest.mark.parametrize(
    "update_mock",
    [
        {"return_value.enabled": False},
        {"return_value.types": 4},
        {"return_value.types": 4062},
        {
            "return_value.options": WebhookNotificationOptions(
                webhook_url="http://example.com", json_payload=JSON_PAYLOAD
            )
        },
        {
            "return_value.options": WebhookNotificationOptions(
                webhook_url="http://10.10.10.10:8123/api/webhook/test-webhook-id",
                json_payload='"{\\"message\\": \\"{{title}}\\"}"',
            )
        },
    ],
    ids=[
        "Disabled",
        "Smaller scope",
        "Bigger scope",
        "Webhook URL",
        "JSON Payload",
    ],
)
async def test_webhook_failing_test(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_overseerr_client: AsyncMock,
    update_mock: dict[str, Any],
) -> None:
    """Test the webhook configuration."""
    mock_overseerr_client.test_webhook_notification_config.return_value = False
    mock_overseerr_client.get_webhook_notification_config.configure_mock(**update_mock)

    await setup_integration(hass, mock_config_entry)

    mock_overseerr_client.test_webhook_notification_config.assert_called_once()
    mock_overseerr_client.set_webhook_notification_config.assert_not_called()


async def test_prefer_internal_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_overseerr_client: AsyncMock,
) -> None:
    """Test the integration prefers internal IP."""
    mock_overseerr_client.test_webhook_notification_config.return_value = False
    hass.config.internal_url = "http://192.168.0.123:8123"
    hass.config.external_url = "https://www.example.com"
    await hass.async_block_till_done(wait_background_tasks=True)
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_overseerr_client.test_webhook_notification_config.call_args_list[0][0][0]
        == "http://192.168.0.123:8123/api/webhook/test-webhook-id"
    )
    assert (
        mock_overseerr_client.test_webhook_notification_config.call_args_list[1][0][0]
        == "https://www.example.com/api/webhook/test-webhook-id"
    )
