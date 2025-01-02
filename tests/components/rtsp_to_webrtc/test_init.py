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
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import SERVER_URL, STREAM_SOURCE, ComponentSetup

from tests.common import MockConfigEntry
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


@pytest.mark.usefixtures("rtsp_to_webrtc_client")
async def test_setup_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful setup and unload."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "deprecated")

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert not issue_registry.async_get_issue(DOMAIN, "deprecated")


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
    hass_ws_client: WebSocketGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful response from RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        json={"sdp64": base64.b64encode(ANSWER_SDP.encode("utf-8")).decode("utf-8")},
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": OFFER_SDP,
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": ANSWER_SDP,
    }

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
    hass_ws_client: WebSocketGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test a transient failure talking to RTSPtoWebRTC server."""
    await setup_integration()

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        exc=aiohttp.ClientError,
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": OFFER_SDP,
        }
    )

    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "RTSPtoWebRTC server communication failure: ",
    }
