"""Tests for RTSPtoWebRTC initialization."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import Mock, patch

import aiohttp
import pytest
import rtsp_to_webrtc

from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.components.camera.webrtc import WebRTCAnswer, WebRTCSendMessage
from homeassistant.components.rtsp_to_webrtc import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .conftest import SERVER_URL, STREAM_SOURCE, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker

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


@pytest.mark.usefixtures("mock_camera", "rtsp_to_webrtc_client")
async def test_offer_for_stream_source(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful response from RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        json={"sdp64": base64.b64encode(ANSWER_SDP.encode("utf-8")).decode("utf-8")},
    )

    camera = get_camera_from_entity_id(hass, "camera.demo_camera")
    send_message = Mock(spec_set=WebRTCSendMessage)
    await camera.async_handle_async_webrtc_offer(OFFER_SDP, "session_id", send_message)
    send_message.assert_called_once_with(WebRTCAnswer(ANSWER_SDP))

    # Validate request parameters were sent correctly
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][2] == {
        "sdp64": base64.b64encode(OFFER_SDP.encode("utf-8")).decode("utf-8"),
        "url": STREAM_SOURCE,
    }


@pytest.mark.usefixtures("mock_camera", "rtsp_to_webrtc_client")
async def test_offer_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: ComponentSetup,
) -> None:
    """Test a transient failure talking to RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        exc=aiohttp.ClientError,
    )

    camera = get_camera_from_entity_id(hass, "camera.demo_camera")
    send_message = Mock(spec_set=WebRTCSendMessage)
    with pytest.raises(
        HomeAssistantError,
        match="RTSPtoWebRTC server communication failure: ",
    ):
        await camera.async_handle_async_webrtc_offer(
            OFFER_SDP, "session_id", send_message
        )
    send_message.assert_not_called()
