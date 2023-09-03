"""Fixtures for UniFi Network methods."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.unifi.controller import RETRY_TIMER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


class WebsocketStateManager(asyncio.Event):
    """Keep an async event that simules websocket context manager.

    Prepares disconnect and reconnect flows.
    """

    def __init__(self, hass: HomeAssistant):
        """Store hass object and initialize asyncio.Event."""
        self.hass = hass
        super().__init__()

    async def disconnect(self):
        """Mark future as done to make 'await self.api.start_websocket' return."""
        self.set()
        await self.hass.async_block_till_done()

    async def reconnect(self, fail=False):
        """Set up new future to make 'await self.api.start_websocket' block.

        Fail will make 'await self.api.start_websocket' return immediately.
        """
        if not fail:
            self.clear()
        new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
        async_fire_time_changed(self.hass, new_time)
        await self.hass.async_block_till_done()


@pytest.fixture(autouse=True, name="websocket_state")
def websocket_context_manager(hass: HomeAssistant) -> WebsocketStateManager:
    """Async event representing websocket context manager."""
    return WebsocketStateManager(hass)


@pytest.fixture(autouse=True)
def websocket_mock(websocket_state):
    """Mock aiounifi websocket."""
    with patch("aiounifi.Controller.start_websocket") as ws_mock:
        # with patch("aiounifi.controller.Connectivity.websocket") as ws_mock:
        ws_mock.side_effect = websocket_state.wait
        yield ws_mock


@pytest.fixture(autouse=True)
def mock_unifi_websocket():
    """No real websocket allowed."""

    def make_websocket_call(
        controller,
        *,
        message: MessageKey | None = None,
        data: list[dict] | dict | None = None,
    ):
        """Generate a websocket call."""
        if data and not message:
            controller.api.messages.handler(data)
        elif data and message:
            if not isinstance(data, list):
                data = [data]
            controller.api.messages.handler(
                {
                    "meta": {"message": message.value},
                    "data": data,
                }
            )
        else:
            raise NotImplementedError

    return make_websocket_call


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow._async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture
def mock_device_registry(hass):
    """Mock device registry."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
            "00:00:00:00:00:04",
            "00:00:00:00:00:05",
            "00:00:00:00:01:01",
            "00:00:00:00:02:02",
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )
