"""Tests the init part of the Loqed integration."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from loqedAPI import loqed
import pytest

from homeassistant.components.loqed.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.network import get_url
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_fixture,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)
from tests.typing import ClientSessionGenerator


async def test_webhook_accepts_valid_message(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    integration: MockConfigEntry,
    lock: loqed.Lock,
) -> None:
    """Test webhook called with valid message."""
    await async_setup_component(hass, "http", {"http": {}})
    client = await hass_client_no_auth()
    processed_message = await async_load_json_object_fixture(
        hass, "lock_going_to_nightlock.json", DOMAIN
    )
    lock.receiveWebhook = AsyncMock(return_value=processed_message)

    message = await async_load_fixture(hass, "battery_update.json", DOMAIN)
    timestamp = 1653304609
    await client.post(
        f"/api/webhook/{integration.data[CONF_WEBHOOK_ID]}",
        data=message,
        headers={"timestamp": str(timestamp), "hash": "incorrect hash"},
    )
    lock.receiveWebhook.assert_called()


async def test_setup_webhook_in_bridge(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test webhook setup in loqed bridge."""
    config: dict[str, Any] = {DOMAIN: {}}
    config_entry.add_to_hass(hass)

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)
    webhooks_fixture = await async_load_json_array_fixture(
        hass, "get_all_webhooks.json", DOMAIN
    )
    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with(f"{get_url(hass)}/api/webhook/Webhook_id")


async def test_webhook_prefers_internal_url(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test webhook actually prefers internal url."""
    await hass.config.async_update(
        internal_url="http://192.168.1.10:8123",
        external_url="https://this-is-external-url.hass.nabu.casa",
    )

    config_entry.add_to_hass(hass)

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    webhooks_fixture = await async_load_json_array_fixture(
        hass, "get_all_webhooks.json", DOMAIN
    )
    webhooks_fixture[0]["url"] = f"{hass.config.internal_url}/api/webhook/Webhook_id"

    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with(
        f"{hass.config.internal_url}/api/webhook/Webhook_id"
    )


async def test_ensure_webhooks_removes_stale_webhooks(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test that stale webhooks with the same ID but different URL are removed."""
    await hass.config.async_update(
        internal_url="http://192.168.1.10:8123",
        external_url="https://this-is-external-url.hass.nabu.casa",
    )

    config_entry.add_to_hass(hass)
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    stale_webhook = {
        "id": 14,
        "url": f"192.168.14.233/api/webhook/{webhook_id}",
    }
    another_stale_webhook = {
        "id": 4,
        "url": f"{hass.config.external_url}/api/webhook/{webhook_id}",
    }
    new_webhook = {
        "id": 15,
        "url": f"{hass.config.internal_url}/api/webhook/{webhook_id}",
    }

    lock.getWebhooks = AsyncMock(
        side_effect=[
            [stale_webhook, another_stale_webhook],
            [stale_webhook, another_stale_webhook, new_webhook],
        ]
    )

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_once()
    assert lock.deleteWebhook.call_count == 2
    lock.deleteWebhook.assert_has_calls([call(14), call(4)], any_order=True)


async def test_ensure_webhooks_handles_bridge_error_on_cleanup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lock: loqed.Lock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that stale webhook cleanup handles bridge connection errors smoothly."""
    await hass.config.async_update(internal_url="http://192.168.1.10:8123")

    config_entry.add_to_hass(hass)
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    stale_webhook = {
        "id": 14,
        "url": f"https://this-is-external-url.hass.nabu.casa/api/webhook/{webhook_id}",
    }
    new_webhook = {
        "id": 15,
        "url": f"{hass.config.internal_url}/api/webhook/{webhook_id}",
    }

    lock.getWebhooks = AsyncMock(
        side_effect=[[stale_webhook], [stale_webhook, new_webhook]]
    )

    lock.deleteWebhook = AsyncMock(side_effect=aiohttp.ClientError)

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    lock.deleteWebhook.assert_called_once_with(14)

    assert "Could not remove stale webhook from LOQED bridge" in caplog.text


async def test_cannot_connect_to_bridge_will_retry(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test webhook setup in loqed bridge."""
    config: dict[str, Any] = {DOMAIN: {}}
    config_entry.add_to_hass(hass)

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock", side_effect=aiohttp.ClientError
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_after_bridge_webhook_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lock: loqed.Lock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup is reentrant after Loqed bridge webhook setup fails.

    The first setup fails while checking the Loqed bridge webhooks. Setup must
    be reentrant so the retry can complete.
    """
    config_entry.add_to_hass(hass)

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)
    webhooks_fixture = await async_load_json_array_fixture(
        hass, "get_all_webhooks.json", DOMAIN
    )
    lock.getWebhooks = AsyncMock(
        side_effect=[ConfigEntryNotReady, webhooks_fixture, webhooks_fixture]
    )

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
            return_value=lock_status,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY

        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED


async def test_setup_cloudhook_in_bridge(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test webhook setup in loqed bridge."""
    config: dict[str, Any] = {DOMAIN: {}}
    config_entry.add_to_hass(hass)

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)
    webhooks_fixture = await async_load_json_array_fixture(
        hass, "get_all_webhooks.json", DOMAIN
    )
    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value=webhooks_fixture[0]["url"],
        ),
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with(f"{get_url(hass)}/api/webhook/Webhook_id")


async def test_setup_cloudhook_from_entry_in_bridge(
    hass: HomeAssistant, cloud_config_entry: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test webhook setup in loqed bridge."""
    webhooks_fixture = await async_load_json_array_fixture(
        hass, "get_all_webhooks.json", DOMAIN
    )

    config: dict[str, Any] = {DOMAIN: {}}
    cloud_config_entry.add_to_hass(hass)

    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value=webhooks_fixture[0]["url"],
        ),
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with(f"{get_url(hass)}/api/webhook/Webhook_id")


async def test_unload_entry(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test successful unload of entry."""

    assert await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    lock.deleteWebhook.assert_called_with(1)
    assert integration.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_unload_entry_fails(
    hass: HomeAssistant, integration: MockConfigEntry, lock: loqed.Lock
) -> None:
    """Test unsuccessful unload of entry."""
    lock.deleteWebhook = AsyncMock(side_effect=Exception)

    assert not await hass.config_entries.async_unload(integration.entry_id)


@pytest.mark.parametrize("error", [aiohttp.ClientError, TimeoutError])
async def test_unload_entry_with_unreachable_bridge(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    lock: loqed.Lock,
    error: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entry still unloads when the bridge is unreachable."""
    lock.getWebhooks = AsyncMock(side_effect=error)

    assert await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    assert integration.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
    assert "Could not remove webhook from LOQED bridge" in caplog.text
