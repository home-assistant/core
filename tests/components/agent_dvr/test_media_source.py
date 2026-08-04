"""Tests for the Agent DVR media source.

As with test_button.py, the WebRTC session itself is mocked: browsing and
downloading recordings needs a real aiortc RTCPeerConnection and a live
Agent DVR server (see webrtc.py's module docstring for how that protocol
was reverse-engineered and verified). These tests verify that
media_source.py drives that session with the right calls and builds the
right browse tree / cache path from its response.
"""

from unittest.mock import AsyncMock, patch

from homeassistant.components.agent_dvr.const import DOMAIN
from homeassistant.components.agent_dvr.media_source import AgentDVRMediaSource
from homeassistant.components.agent_dvr.webrtc import AgentDVRWebRTCSession
from homeassistant.components.media_source import MediaSourceItem
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker

RECORDING = {
    "ot": 2,
    "oid": 1,
    "fn": "1_2024-01-01_12-00-00_000.mkv",
    "sb": 1234,
    "d": 10,
    "tg": "motion",
}


async def test_browse_servers_cameras_recordings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test browsing from the server root down to a camera's recordings."""
    entry = await init_integration(hass, aioclient_mock)
    source = AgentDVRMediaSource(hass)

    root = await source.async_browse_media(MediaSourceItem(hass, DOMAIN, "", None))
    assert len(root.children) == 1
    assert root.children[0].identifier == entry.entry_id

    cameras = await source.async_browse_media(
        MediaSourceItem(hass, DOMAIN, entry.entry_id, None)
    )
    assert len(cameras.children) == 1
    assert cameras.children[0].identifier == f"{entry.entry_id}|1_2"
    assert cameras.children[0].title == "Front Door"

    with (
        patch.object(AgentDVRWebRTCSession, "connect", AsyncMock()),
        patch.object(AgentDVRWebRTCSession, "close", AsyncMock()),
        patch.object(
            AgentDVRWebRTCSession,
            "get_recordings",
            AsyncMock(return_value=[RECORDING]),
        ),
    ):
        recordings = await source.async_browse_media(
            MediaSourceItem(hass, DOMAIN, f"{entry.entry_id}|1_2", None)
        )

    assert len(recordings.children) == 1
    assert (
        recordings.children[0].identifier == f"{entry.entry_id}|1_2|{RECORDING['fn']}"
    )
    assert recordings.children[0].can_play is True


async def test_resolve_media_downloads_and_caches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tmp_path
) -> None:
    """Test resolving a recording downloads it once and caches it locally."""
    entry = await init_integration(hass, aioclient_mock)
    source = AgentDVRMediaSource(hass)
    hass.config.config_dir = str(tmp_path)

    with (
        patch.object(AgentDVRWebRTCSession, "connect", AsyncMock()),
        patch.object(AgentDVRWebRTCSession, "close", AsyncMock()),
        patch.object(
            AgentDVRWebRTCSession,
            "download_file",
            AsyncMock(return_value=b"fake-video-bytes"),
        ) as mock_download,
    ):
        result = await source.async_resolve_media(
            MediaSourceItem(
                hass, DOMAIN, f"{entry.entry_id}|1_2|{RECORDING['fn']}", None
            )
        )

    mock_download.assert_awaited_once_with(1, 2, RECORDING["fn"])
    assert result.mime_type == "video/x-matroska"
    assert result.url.endswith(RECORDING["fn"])

    cache_path = tmp_path / "www" / DOMAIN / entry.entry_id / RECORDING["fn"]
    assert cache_path.read_bytes() == b"fake-video-bytes"
