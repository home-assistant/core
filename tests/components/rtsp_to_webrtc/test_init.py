"""Tests for RTSPtoWebRTC initialization."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
import rtsp_to_webrtc

from homeassistant.components.rtsp_to_webrtc import DOMAIN
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import SERVER_URL, STREAM_SOURCE, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

# The webrtc component does not inspect the details of the offer and answer,
# and is only a pass through.
OFFER_SDP = "v=0\r\no=carol 28908764872 28908764872 IN IP4 100.3.6.6\r\n..."
ANSWER_SDP = "v=0\r\no=bob 2890844730 2890844730 IN IP4 host.example.com\r\n..."


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


async def test_setup_success(
    hass: HomeAssistant, rtsp_to_webrtc_client: Any, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


@pytest.mark.parametrize("config_entry_data", [{}])
async def test_invalid_config_entry(
    hass: HomeAssistant, rtsp_to_webrtc_client: Any, setup_integration: ComponentSetup
) -> None:
    """Test a config entry with missing required fields."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_setup_server_failure(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test server responds with a failure on startup."""
    with patch(
        "rtsp_to_webrtc.client.Client.heartbeat",
        side_effect=rtsp_to_webrtc.exceptions.ResponseError(),
    ):
        await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_setup_communication_failure(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test unable to talk to server on startup."""
    with patch(
        "rtsp_to_webrtc.client.Client.heartbeat",
        side_effect=rtsp_to_webrtc.exceptions.ClientError(),
    ):
        await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_offer_for_stream_source(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
    mock_camera: Any,
    rtsp_to_webrtc_client: Any,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful response from RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        json={"sdp64": base64.b64encode(ANSWER_SDP.encode("utf-8")).decode("utf-8")},
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": OFFER_SDP,
        }
    )
    response = await client.receive_json()
    assert response.get("id") == 1
    assert response.get("type") == TYPE_RESULT
    assert response.get("success")
    assert "result" in response
    assert response["result"].get("answer") == ANSWER_SDP
    assert "error" not in response

    # Validate request parameters were sent correctly
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][2] == {
        "sdp64": base64.b64encode(OFFER_SDP.encode("utf-8")).decode("utf-8"),
        "url": STREAM_SOURCE,
    }


async def test_offer_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
    mock_camera: Any,
    rtsp_to_webrtc_client: Any,
    setup_integration: ComponentSetup,
) -> None:
    """Test a transient failure talking to RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        exc=aiohttp.ClientError,
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 2,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": OFFER_SDP,
        }
    )
    response = await client.receive_json()
    assert response.get("id") == 2
    assert response.get("type") == TYPE_RESULT
    assert "success" in response
    assert not response.get("success")
    assert "error" in response
    assert response["error"].get("code") == "web_rtc_offer_failed"
    assert "message" in response["error"]
    assert "RTSPtoWebRTC server communication failure" in response["error"]["message"]
