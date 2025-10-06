"""Tests for the homelink coordinator."""

import asyncio
import time
from unittest.mock import patch

from homelink.model.button import Button
from homelink.model.device import Device
import pytest

from homeassistant.components.gentex_homelink import async_setup_entry
from homeassistant.components.gentex_homelink.const import EVENT_PRESSED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

DOMAIN = "gentex_homelink"

deviceInst = Device(id="TestDevice", name="TestDevice")
deviceInst.buttons = [
    Button(id="Button 1", name="Button 1", device=deviceInst),
    Button(id="Button 2", name="Button 2", device=deviceInst),
    Button(id="Button 3", name="Button 3", device=deviceInst),
]


async def test_get_state_updates(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state updates.

    Tests that get_state calls are called by home assistant, and the homeassistant components respond appropriately to the data returned.
    """
    with patch(
        "homeassistant.components.gentex_homelink.MQTTProvider", autospec=True
    ) as MockProvider:
        instance = MockProvider.return_value
        instance.discover.return_value = [deviceInst]
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

        provider = config_entry.runtime_data.provider
        state_data = {
            "type": "state",
            "data": {
                "Button 1": {"requestId": "rid1", "timestamp": time.time()},
                "Button 2": {"requestId": "rid2", "timestamp": time.time()},
                "Button 3": {"requestId": "rid3", "timestamp": time.time()},
            },
        }

        # Test successful setup and first data fetch. The buttons should be unknown at the start
        await hass.async_block_till_done(wait_background_tasks=True)
        states = hass.states.async_all()
        assert states, "No states were loaded"
        assert all(state != STATE_UNAVAILABLE for state in states), (
            "At least one state was not initialized as STATE_UNAVAILABLE"
        )
        buttons_unknown = [s.state == "unknown" for s in states]
        assert all(buttons_unknown), (
            "At least one button state was not initialized to unknown"
        )

        provider.listen.mock_calls[0].args[0](None, state_data)

        await hass.async_block_till_done(wait_background_tasks=True)
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
        await asyncio.sleep(0.01)
        states = hass.states.async_all()

        assert all(state != STATE_UNAVAILABLE for state in states), (
            "Some button became unavailable"
        )
        buttons_pressed = [s.attributes["event_type"] == EVENT_PRESSED for s in states]
        assert all(buttons_pressed), "At least one button was not pressed"


async def test_request_sync(hass: HomeAssistant) -> None:
    """Test that the config entry is reloaded when a requestSync request is sent."""
    updatedDeviceInst = Device(id="TestDevice", name="TestDevice")
    updatedDeviceInst.buttons = [
        Button(id="Button 1", name="New Button 1", device=deviceInst),
        Button(id="Button 2", name="New Button 2", device=deviceInst),
        Button(id="Button 3", name="New Button 3", device=deviceInst),
    ]

    with patch(
        "homeassistant.components.gentex_homelink.MQTTProvider", autospec=True
    ) as MockProvider:
        instance = MockProvider.return_value
        instance.discover.side_effect = [[deviceInst], [updatedDeviceInst]]
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

        # Check to see if the correct buttons names were loaded
        comp = er.async_get(hass)
        button_names = {"Button 1", "Button 2", "Button 3"}
        registered_button_names = {b.original_name for b in comp.entities.values()}

        assert button_names == registered_button_names, (
            "Expect button names to be correct for the initial config"
        )

        provider = config_entry.runtime_data.provider
        coordinator = config_entry.runtime_data.coordinator

        with patch.object(
            coordinator.hass.config_entries, "async_reload"
        ) as async_reload_mock:
            # Mimic request sync event
            state_data = {
                "type": "requestSync",
            }
            # async reload should not be called yet
            async_reload_mock.assert_not_called()
            # Send the request sync
            provider.listen.mock_calls[0].args[0](None, state_data)
            # Wait for the request to be processed
            await hass.async_block_till_done(wait_background_tasks=True)
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            await asyncio.sleep(0.01)

            # Now async reload should have been called
            async_reload_mock.assert_called()
