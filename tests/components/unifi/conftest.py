"""Fixtures for UniFi Network methods."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.controller import RETRY_TIMER
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.unifi.test_controller import DEFAULT_CONFIG_ENTRY_ID
from tests.test_util.aiohttp import AiohttpClientMocker


class WebsocketStateManager(asyncio.Event):
    """Keep an async event that simules websocket context manager.

    Prepares disconnect and reconnect flows.
    """

    def __init__(self, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
        """Store hass object and initialize asyncio.Event."""
        self.hass = hass
        self.aioclient_mock = aioclient_mock
        super().__init__()

    async def disconnect(self):
        """Mark future as done to make 'await self.api.start_websocket' return."""
        self.set()
        await self.hass.async_block_till_done()

    async def reconnect(self, fail=False):
        """Set up new future to make 'await self.api.start_websocket' block.

        Mock api calls done by 'await self.api.login'.
        Fail will make 'await self.api.start_websocket' return immediately.
        """
        controller = self.hass.data[UNIFI_DOMAIN][DEFAULT_CONFIG_ENTRY_ID]
        self.aioclient_mock.get(
            f"https://{controller.host}:1234", status=302
        )  # Check UniFi OS
        self.aioclient_mock.post(
            f"https://{controller.host}:1234/api/login",
            json={"data": "login successful", "meta": {"rc": "ok"}},
            headers={"content-type": CONTENT_TYPE_JSON},
        )

        if not fail:
            self.clear()
        new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
        async_fire_time_changed(self.hass, new_time)
        await self.hass.async_block_till_done()


@pytest.fixture(autouse=True)
def websocket_mock(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Mock 'await self.api.start_websocket' in 'UniFiController.start_websocket'."""
    websocket_state_manager = WebsocketStateManager(hass, aioclient_mock)
    with patch("aiounifi.Controller.start_websocket") as ws_mock:
        ws_mock.side_effect = websocket_state_manager.wait
        yield websocket_state_manager


@pytest.fixture(autouse=True)
def mock_unifi_websocket(hass):
    """No real websocket allowed."""

    def make_websocket_call(
        *,
        message: MessageKey | None = None,
        data: list[dict] | dict | None = None,
    ):
        """Generate a websocket call."""
        controller = hass.data[UNIFI_DOMAIN][DEFAULT_CONFIG_ENTRY_ID]
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
            "00:00:00:00:00:06",
            "00:00:00:00:01:01",
            "00:00:00:00:02:02",
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )
