"""Tests for the homelink coordinator."""

import logging
import time
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.gentex_homelink import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .mocks.mock_device import MockDevice

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

DOMAIN = "gentex_homelink"


def get_state_data():
    """Get the state of each request."""
    return [
        # initial request
        (
            None,
            {
                "Button 1": {"requestId": "id", "timestamp": time.time()},
                "Button 2": {"requestId": "id", "timestamp": time.time()},
                "Button 3": {"requestId": "id", "timestamp": time.time()},
            },
        ),
        # Same request repeated
        (
            None,
            {
                "Button 1": {"requestId": "id", "timestamp": time.time()},
                "Button 2": {"requestId": "id", "timestamp": time.time()},
                "Button 3": {"requestId": "id", "timestamp": time.time()},
            },
        ),
        # New ID and time
        (
            None,
            {
                "Button 1": {"requestId": "id2", "timestamp": time.time() + 100},
                "Button 2": {"requestId": "id2", "timestamp": time.time() + 100},
                "Button 3": {"requestId": "id2", "timestamp": time.time() + 100},
            },
        ),
        # new ID and time repeated
        (
            None,
            {
                "Button 1": {"requestId": "id2", "timestamp": time.time() + 100},
                "Button 2": {"requestId": "id2", "timestamp": time.time() + 100},
                "Button 3": {"requestId": "id2", "timestamp": time.time() + 100},
            },
        ),
        # No data
        ({}, {}),
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
    with patch(
        "homeassistant.components.gentex_homelink.Provider", autospec=True
    ) as MockProvider:
        instance = MockProvider.return_value
        instance.get_state.return_value = (None, {})
        instance.discover.side_effect = [
            [MockDevice()],
            [MockDevice(name="TestDevice2")],
        ]
        instance.get_state.side_effect = get_state_data()
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

        # Assert configuration worked without errors
        assert result

        # Test successful setup and first data fetch. The buttons should be off at the start
        logging.info("Initial sync")
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        logging.info(states)
        assert (state != STATE_UNAVAILABLE for state in states)
        buttons_off = [s.state == "off" for s in states]
        assert all(buttons_off)

        logging.info(
            "Fetch data again. Buttons should be off because the request has the same id"
        )
        freezer.tick(5)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button is still unavailable"
        )
        buttons_off = [s.state == "off" for s in states]

        logging.info(
            "Fetch data again. Buttons should be on because the request has a different timestamp and id"
        )
        freezer.tick(100)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_on = [s.state == "on" for s in states]
        assert all(buttons_on), "At least one button failed to turn on"

        logging.info(
            "Fetch data again. Buttons should be off because the id is the same"
        )
        freezer.tick(15)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        assert (state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_off = [s.state == "off" for s in states]
        assert all(buttons_off), (
            "At least one button failed to turn off after the designated time"
        )
