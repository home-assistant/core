"""Tests for the homelink coordinator."""

import logging
import time
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.gentex_homelink import async_setup_entry
from homeassistant.components.gentex_homelink.const import (
    EVENT_OFF,
    EVENT_PRESSED,
    EVENT_TIMEOUT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .mocks.mock_provider import MockProvider

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)
DOMAIN = "gentex_homelink"


def get_state_data():
    """Get the state of each request."""
    return [
        # initial request
        {
            "Button 1": {"requestId": "id", "timestamp": time.time()},
            "Button 2": {"requestId": "id", "timestamp": time.time()},
            "Button 3": {"requestId": "id", "timestamp": time.time()},
        },
        # Same request repeated
        {
            "Button 1": {"requestId": "id", "timestamp": time.time()},
            "Button 2": {"requestId": "id", "timestamp": time.time()},
            "Button 3": {"requestId": "id", "timestamp": time.time()},
        },
        # New ID and time
        {
            "Button 1": {"requestId": "id2", "timestamp": time.time() + 100},
            "Button 2": {"requestId": "id2", "timestamp": time.time() + 100},
            "Button 3": {"requestId": "id2", "timestamp": time.time() + 100},
        },
        # new ID and time repeated
        {
            "Button 1": {"requestId": "id2", "timestamp": time.time() + 100},
            "Button 2": {"requestId": "id2", "timestamp": time.time() + 100},
            "Button 3": {"requestId": "id2", "timestamp": time.time() + 100},
        },
        # No data
        {},
    ]


@pytest.mark.asyncio
async def test_get_state_updates(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state updates.

    Tests that get_state calls are called by home assistant, and the homeassistant components respond appropriately to the data returned.
    This is done as one test to share the freezer state, in order to simulate a continuous stream of messages like we get in the real world.
    """
    with patch("homeassistant.components.gentex_homelink.MQTTProvider", MockProvider):
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
        state_data = get_state_data()

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

        freezer.tick(1)
        provider._call_listeners(state_data[0])
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()

        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_pressed = [s.attributes["event_type"] == EVENT_PRESSED for s in states]
        assert all(buttons_pressed), "At least one button was not pressed"
        _LOGGER.info(
            "Fetch data again. Buttons should be off because more than 10s has elapsed"
        )

        freezer.tick(EVENT_TIMEOUT + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button is still unavailable"
        )

        buttons_off = [s.attributes["event_type"] == EVENT_OFF for s in states]
        assert all(buttons_off), "Some button was not Off"
        _LOGGER.info(
            "Fetch data again. Buttons should be on because the request has a different timestamp and id"
        )
        provider._call_listeners(state_data[2])

        freezer.tick(1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()

        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_pressed = [s.attributes["event_type"] == EVENT_PRESSED for s in states]
        assert all(buttons_pressed), "At least one button was not pressed"

        _LOGGER.info("Fetch data again. Buttons should be off the time has expired")
        freezer.tick(EVENT_TIMEOUT + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        states = hass.states.async_all()
        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_off = [s.attributes["event_type"] == EVENT_OFF for s in states]
        assert all(buttons_off), (
            "At least one button failed to turn off after the designated time"
        )
