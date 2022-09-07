"""Test the init file of Twilio."""
from collections.abc import Awaitable
from typing import Callable

import aiohttp
from aiohttp.test_utils import TestClient

from homeassistant.components import twilio
from homeassistant.components.twilio.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs


async def test_setup(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
) -> None:
    """Test integration failed due to an error."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"account_sid": "12345678", "auth_token": "token"}}
    )
    assert hass.config_entries.async_entries(DOMAIN)
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "deprecated_yaml"


async def test_config_flow_registers_webhook(
    hass: HomeAssistant, hass_client_no_auth: Callable[[], Awaitable[TestClient]]
):
    """Test setting up Twilio and sending webhook."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    twilio_events = []

    @callback
    def handle_event(event):
        """Handle Twilio event."""
        twilio_events.append(event)

    hass.bus.async_listen(twilio.RECEIVED_DATA, handle_event)

    client = await hass_client_no_auth()
    await client.post("/api/webhook/ABCD", data={"hello": "twilio"})

    assert len(twilio_events) == 1
    assert twilio_events[0].data["webhook_id"] == "ABCD"
    assert twilio_events[0].data["hello"] == "twilio"


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
