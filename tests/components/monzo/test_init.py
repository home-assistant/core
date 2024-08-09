"""Tests for the Monzo component."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components import cloud
from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.monzo.const import (
    DOMAIN,
    EVENT_TRANSACTION_CREATED,
    MONZO_EVENT,
)
from homeassistant.components.webhook import (
    DOMAIN as WEBHOOK_DOMAIN,
    async_generate_url,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_ACCOUNTS, MonzoMockConfigEntry

from tests.common import MockConfigEntry
from tests.components.cloud import mock_cloud
from tests.typing import ClientSessionGenerator


@dataclass
class WebhookSetupData:
    """A collection of data set up by the webhook_setup fixture."""

    hass: HomeAssistant
    client: TestClient
    webhook_url: str
    event_listener: Mock


@pytest.fixture
async def webhook_setup(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MonzoMockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> WebhookSetupData:
    """Set up integration, client and webhook url."""

    await setup_integration(hass, polling_config_entry)
    client = await hass_client_no_auth()
    webhook_id = next(iter(polling_config_entry.runtime_data.webhook_ids))
    webhook_url = async_generate_url(hass, webhook_id)
    event_listener = Mock()
    hass.bus.async_listen(MONZO_EVENT, event_listener)

    return WebhookSetupData(hass, client, webhook_url, event_listener)


@pytest.mark.usefixtures("current_request_with_host")
async def test_webhook_fires_transaction_created(
    webhook_setup: WebhookSetupData,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test calling a webhook fires transaction_created event."""

    resp = await webhook_setup.client.post(
        urlparse(webhook_setup.webhook_url).path,
        json={
            "type": EVENT_TRANSACTION_CREATED,
            "data": {"account_id": TEST_ACCOUNTS[0]["id"]},
        },
    )
    # Wait for remaining tasks to complete.
    await webhook_setup.hass.async_block_till_done()

    assert resp.ok
    webhook_setup.event_listener.assert_called_once()

    resp.close()


@pytest.mark.usefixtures("current_request_with_host")
async def test_webhook_with_unexpected_type(
    webhook_setup: WebhookSetupData,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test calling a webhook with an unexpected event type."""

    resp = await webhook_setup.client.post(
        urlparse(webhook_setup.webhook_url).path,
        json={
            "type": "fail",
            "data": {"account_id": TEST_ACCOUNTS[0]["id"]},
        },
    )
    # Wait for remaining tasks to complete.
    await webhook_setup.hass.async_block_till_done()

    assert resp.ok
    webhook_setup.event_listener.assert_not_called()

    assert "unexpected event type" in caplog.text


async def test_cloudhook(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MonzoMockConfigEntry,
) -> None:
    """Test cloudhook setup."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
        patch(
            "homeassistant.components.monzo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as fake_delete_cloudhook,
        patch("homeassistant.components.monzo.webhook_generate_url"),
    ):
        await setup_integration(hass, polling_config_entry)

        assert cloud.async_active_subscription(hass) is True

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)
        assert fake_create_cloudhook.call_count == len(TEST_ACCOUNTS)
        assert len(hass.data[WEBHOOK_DOMAIN]) == len(TEST_ACCOUNTS)

        for config_entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(config_entry.entry_id)
            fake_delete_cloudhook.call_count = len(TEST_ACCOUNTS)

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)
        assert len(hass.data[WEBHOOK_DOMAIN]) == 0


async def test_removing_entry_with_cloud_unavailable(
    hass: HomeAssistant, polling_config_entry: MockConfigEntry, monzo: AsyncMock
) -> None:
    """Test handling cloud unavailable when deleting entry."""

    await mock_cloud(hass)
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook",
            side_effect=CloudNotAvailable(),
        ),
        patch(
            "homeassistant.components.monzo.webhook_generate_url",
        ),
    ):
        await setup_integration(hass, polling_config_entry)

        assert cloud.async_active_subscription(hass) is True

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)

        for config_entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(config_entry.entry_id)

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_webhook_fails_without_https(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if set up with cloud link and without https."""
    hass.config.components.add("cloud")
    with (
        patch(
            "homeassistant.helpers.network.get_url",
            return_value="http://example.nabu.casa",
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.monzo.webhook_generate_url"
        ) as mock_async_generate_url,
    ):
        mock_async_generate_url.return_value = "http://example.com"
        await setup_integration(hass, polling_config_entry)

        await hass.async_block_till_done()
        mock_async_generate_url.call_count = len(TEST_ACCOUNTS)

    assert "https and port 443 is required to register the webhook" in caplog.text
