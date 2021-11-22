"""Tests for WebRTC inititalization."""

import base64

import aiohttp
import pytest

from homeassistant.components import webrtc
from homeassistant.components.webrtc.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

STREAM_SOURCE = "rtsp://example.com"
# The webrtc component does not inspect the details of the offer and answer,
# and is only a pass through.
OFFER_SDP = "v=0\r\no=carol 28908764872 28908764872 IN IP4 100.3.6.6\r\n..."
ANSWER_SDP = "v=0\r\no=bob 2890844730 2890844730 IN IP4 host.example.com\r\n..."

SERVER_URL = "http://127.0.0.1:8083"

CONFIG_ENTRY_DATA = {"rtsp_to_webrtc_url": SERVER_URL}


async def async_setup_webrtc(hass: HomeAssistant):
    """Set up the component."""
    return await async_setup_component(hass, DOMAIN, {})


async def test_supported_stream_source(hass: HomeAssistant) -> None:
    """Test successful setup."""
    assert webrtc.is_suported_stream_source("rtsp://")
    assert not webrtc.is_suported_stream_source("http://")
    assert not webrtc.is_suported_stream_source("rtsp")


async def test_setup_success(hass: HomeAssistant) -> None:
    """Test successful setup and unload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await async_setup_webrtc(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test a config entry with missing required fields."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    assert await async_setup_webrtc(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_offer_for_stream_source(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test successful response from RTSPtoWebRTC server."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await async_setup_webrtc(hass)

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        json={"sdp64": base64.b64encode(ANSWER_SDP.encode("utf-8")).decode("utf-8")},
    )

    answer_sdp = await webrtc.async_offer_for_stream_source(
        hass, OFFER_SDP, STREAM_SOURCE
    )
    assert answer_sdp == ANSWER_SDP


async def test_offer_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a transient failure talking to RTSPtoWebRTC server."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await async_setup_webrtc(hass)

    aioclient_mock.post(
        f"{SERVER_URL}/stream",
        exc=aiohttp.ClientError,
    )

    with pytest.raises(
        HomeAssistantError, match=r"WebRTC server communication failure.*"
    ):
        await webrtc.async_offer_for_stream_source(hass, OFFER_SDP, STREAM_SOURCE)


async def test_integration_not_loaded(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invoking the integration when not loaded."""
    with pytest.raises(HomeAssistantError, match=r"webrtc integration is not set up.*"):
        await webrtc.async_offer_for_stream_source(hass, OFFER_SDP, STREAM_SOURCE)
