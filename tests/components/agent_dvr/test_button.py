"""Tests for the Agent DVR PTZ direction button platform.

The WebRTC session itself (connect/ptz_move/ptz_stop/close) is mocked
here rather than exercised end-to-end: it needs a real aiortc
RTCPeerConnection and a live Agent DVR server to negotiate against, which
is exactly what was used to reverse-engineer and verify the protocol in
the first place (see webrtc.py's module docstring). These tests instead
verify that button.py drives that session with the right calls.
"""

from unittest.mock import AsyncMock, patch

from homeassistant.components.agent_dvr.webrtc import AgentDVRWebRTCSession
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_ptz_left_button_pulses_and_stops(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test pressing a PTZ button moves the camera, then stops it."""
    await init_integration(hass, aioclient_mock)

    with (
        patch.object(AgentDVRWebRTCSession, "connect", AsyncMock()),
        patch.object(AgentDVRWebRTCSession, "close", AsyncMock()),
        patch.object(AgentDVRWebRTCSession, "ptz_move", AsyncMock()) as mock_move,
        patch.object(AgentDVRWebRTCSession, "ptz_stop", AsyncMock()) as mock_stop,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.desktop_front_door_ptz_left"},
            blocking=True,
        )

    mock_move.assert_awaited_once_with(1, 2, AgentDVRWebRTCSession.PTZ_LEFT)
    mock_stop.assert_awaited_once_with(1, 2)
