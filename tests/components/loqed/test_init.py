"""Tests the init part of the Loqed integration."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from loqedAPI import loqed

from homeassistant.components.loqed.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


async def test_webhook_accepts_valid_message(
    hass: HomeAssistant,
    hass_client_no_auth,
    integration: MockConfigEntry,
    lock: loqed.Lock,
):
    """Test webhook called with valid message."""
    await async_setup_component(hass, "http", {"http": {}})
    client = await hass_client_no_auth()
    processed_message = json.loads(load_fixture("loqed/lock_going_to_nightlock.json"))
    lock.receiveWebhook = AsyncMock(return_value=processed_message)

    message = load_fixture("loqed/battery_update.json")
    timestamp = 1653304609
    await client.post(
        f"/api/webhook/{integration.data[CONF_WEBHOOK_ID]}",
        data=message,
        headers={"timestamp": str(timestamp), "hash": "incorrect hash"},
    )
    lock.receiveWebhook.assert_called()


async def test_setup_webhook_in_bridge(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
):
    """Test webhook setup in loqed bridge."""
    config: dict[str, Any] = {DOMAIN: {}}
    config_entry.add_to_hass(hass)

    lock_status = json.loads(load_fixture("loqed/status_ok.json"))
    webhooks_fixture = json.loads(load_fixture("loqed/get_all_webhooks.json"))
    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock), patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
    ), patch(
        "homeassistant.components.webhook.async_generate_url",
        return_value="http://hook_id",
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with("http://hook_id")


async def test_unload_entry(hass, integration: MockConfigEntry, lock: loqed.Lock):
    """Test successful unload of entry."""

    assert await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    lock.deleteWebhook.assert_called_with(1)
    assert integration.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_unload_entry_fails(hass, integration: MockConfigEntry, lock: loqed.Lock):
    """Test unsuccessful unload of entry."""
    lock.deleteWebhook = AsyncMock(side_effect=Exception)

    assert not await hass.config_entries.async_unload(integration.entry_id)
