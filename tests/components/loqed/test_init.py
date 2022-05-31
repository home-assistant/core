"""Tests the init part of the Loqed integration."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from loqedAPI import loqed

from homeassistant.components.loqed.const import (
    CONF_COORDINATOR,
    CONF_WEBHOOK_INDEX,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


async def test_webhook_rejects_invalid_message(
    hass: HomeAssistant,
    hass_client_no_auth,
    integration: MockConfigEntry,
):
    """Test webhook called with invalid message."""
    await async_setup_component(hass, "http", {"http": {}})
    client = await hass_client_no_auth()

    coordinator = hass.data[DOMAIN][integration.entry_id][CONF_COORDINATOR]

    with patch.object(coordinator, "async_set_updated_data") as mock:
        message = load_fixture("loqed/battery_update.json")
        timestamp = 1653304609
        await client.post(
            f"/api/webhook/{integration.data[CONF_WEBHOOK_ID]}",
            data=message,
            headers={"timestamp": str(timestamp), "hash": "incorrect hash"},
        )

    mock.assert_not_called()


async def test_setup_webhook_in_bridge(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
):
    """Test webhook setup in loqed bridge."""
    config: dict[str, Any] = {DOMAIN: {CONF_COORDINATOR: ""}}
    config_entry.add_to_hass(hass)

    lock_status = json.loads(load_fixture("loqed/status_ok.json"))
    webhooks_fixture = json.loads(load_fixture("loqed/get_all_webhooks.json"))
    lock.getWebhooks = AsyncMock(side_effect=[[], webhooks_fixture])

    with patch(
        "homeassistant.components.webhook.async_generate_url",
        return_value=webhooks_fixture[0]["url"],
    ), patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock), patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    lock.registerWebhook.assert_called_with(webhooks_fixture[0]["url"])


async def test_unload_entry(hass, integration: MockConfigEntry, lock: loqed.Lock):
    """Test successful unload of entry."""
    webhook_index = hass.data[DOMAIN][integration.entry_id][CONF_WEBHOOK_INDEX]

    assert await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    lock.deleteWebhook.assert_called_with(webhook_index)
    assert integration.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
