"""Tests for the homelink coordinator."""

import asyncio
import json
import logging
import time
from unittest.mock import patch

import pytest

from homeassistant.components.gentex_homelink import async_setup_entry
from homeassistant.components.gentex_homelink.const import EVENT_PRESSED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)
DOMAIN = "gentex_homelink"


async def test_get_state_updates(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state updates.

    Tests that get_state calls are called by home assistant, and the homeassistant components respond appropriately to the data returned.
    """
    with patch("homeassistant.components.gentex_homelink.MQTTProvider", autospec=True):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=None,
            version=1,
            data={
                "auth_implementation": "gentex_homelink",
                "token": {"expires_at": time.time() + 10000, "access_token": ""},
                "last_update_id": None,
            },
            state=ConfigEntryState.LOADED,
        )
        config_entry.add_to_hass(hass)
        result = await async_setup_entry(hass, config_entry)

        provider = config_entry.runtime_data.provider
        state_data = {
            "Button 1": {"requestId": "id", "timestamp": time.time()},
            "Button 2": {"requestId": "id", "timestamp": time.time()},
            "Button 3": {"requestId": "id", "timestamp": time.time()},
        }

        # Assert configuration worked without errors
        assert result

        # Test successful setup and first data fetch. The buttons should be unknown at the start
        _LOGGER.info("Initial sync")
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()

        assert (state != STATE_UNAVAILABLE for state in states)
        buttons_unknown = [s.state == "unknown" for s in states]
        assert all(buttons_unknown)

        _LOGGER.info("Fire first event. Buttons should be on")

        provider._on_message(None, None, json.dumps(state_data))

        await hass.async_block_till_done(wait_background_tasks=True)
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
        await asyncio.sleep(0.01)
        states = hass.states.async_all()

        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_pressed = [s.attributes["event_type"] == EVENT_PRESSED for s in states]
        assert all(buttons_pressed), "At least one button was not pressed"
