"""Tests for RTSPtoWebRTC initialization."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import Any, TypeVar
from unittest.mock import patch

import pytest
import rtsp_to_webrtc

from homeassistant.components import camera
from homeassistant.components.rtsp_to_webrtc import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

STREAM_SOURCE = "rtsp://example.com"
SERVER_URL = "http://127.0.0.1:8083"

CONFIG_ENTRY_DATA = {"server_url": SERVER_URL}

# Typing helpers
ComponentSetup = Callable[[], Awaitable[None]]
_T = TypeVar("_T")
YieldFixture = Generator[_T, None, None]


@pytest.fixture(autouse=True)
async def webrtc_server() -> None:
    """Patch client library to force usage of RTSPtoWebRTC server."""
    with patch(
        "rtsp_to_webrtc.client.WebClient.heartbeat",
        side_effect=rtsp_to_webrtc.exceptions.ResponseError(),
    ):
        yield


@pytest.fixture
async def mock_camera(hass) -> AsyncGenerator[None, None]:
    """Initialize a demo camera platform."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        return_value=b"Test",
    ), patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value=STREAM_SOURCE,
    ):
        yield


@pytest.fixture
async def config_entry_data() -> dict[str, Any]:
    """Fixture for MockConfigEntry data."""
    return CONFIG_ENTRY_DATA


@pytest.fixture
def config_entry_options() -> dict[str, Any] | None:
    """Fixture to set initial config entry options."""
    return None


@pytest.fixture
async def config_entry(
    config_entry_data: dict[str, Any],
    config_entry_options: dict[str, Any] | None,
) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN, data=config_entry_data, options=config_entry_options
    )


@pytest.fixture
async def rtsp_to_webrtc_client() -> None:
    """Fixture for mock rtsp_to_webrtc client."""
    with patch("rtsp_to_webrtc.client.Client.heartbeat"):
        yield


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> YieldFixture[ComponentSetup]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    yield func
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED
