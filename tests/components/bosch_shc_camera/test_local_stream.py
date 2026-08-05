"""Tests for local_stream.py — LOCAL-only RTSP session + TLS proxy wiring."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.local_stream import (
    async_start_local_stream,
    async_stop_local_stream,
)
from homeassistant.core import HomeAssistant

_MOD = "homeassistant.components.bosch_shc_camera.local_stream"

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _put_cm(status: int, payload: dict[str, Any]) -> MagicMock:
    """Build an async-context-manager mock matching aiohttp's session.put()."""
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=__import__("json").dumps(payload))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _session_cm(put_cm: MagicMock) -> MagicMock:
    """Build the async_bosch_cloud_session_cm(...) async-with target."""
    session = MagicMock()
    session.put = MagicMock(return_value=put_cm)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class _FakeCoordinator:
    """Minimal stand-in exposing only what local_stream.py reads."""

    def __init__(self, hass: HomeAssistant, token: str = "test-token") -> None:
        self.hass = hass
        self.token = token

    def get_quality_params(self, cam_id: str) -> tuple[bool, int]:
        return (False, 2)


async def test_returns_none_without_a_token(hass: HomeAssistant) -> None:
    """No bearer token at all — never even attempts the PUT."""
    coordinator = _FakeCoordinator(hass, token="")
    result = await async_start_local_stream(coordinator, CAM_ID, {}, {})
    assert result is None


async def test_returns_none_on_non_success_status(hass: HomeAssistant) -> None:
    """A non-200/201 PUT /connection response yields no stream."""
    coordinator = _FakeCoordinator(hass)
    with patch(
        f"{_MOD}.async_bosch_cloud_session_cm",
        return_value=_session_cm(_put_cm(403, {})),
    ):
        result = await async_start_local_stream(coordinator, CAM_ID, {}, {})
    assert result is None


@pytest.mark.parametrize(
    "err",
    [TimeoutError(), aiohttp.ClientError("boom")],
    ids=["timeout", "client_error"],
)
async def test_returns_none_on_connection_error(
    hass: HomeAssistant, err: Exception
) -> None:
    """A network error opening the LOCAL session is swallowed, not raised."""
    coordinator = _FakeCoordinator(hass)
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(side_effect=err)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    with patch(f"{_MOD}.async_bosch_cloud_session_cm", return_value=session_cm):
        result = await async_start_local_stream(coordinator, CAM_ID, {}, {})
    assert result is None


async def test_returns_none_when_credentials_missing(hass: HomeAssistant) -> None:
    """A 200 response with no user/password/urls yields no stream."""
    coordinator = _FakeCoordinator(hass)
    with patch(
        f"{_MOD}.async_bosch_cloud_session_cm",
        return_value=_session_cm(_put_cm(200, {"user": "u"})),
    ):
        result = await async_start_local_stream(coordinator, CAM_ID, {}, {})
    assert result is None


async def test_returns_none_for_unsafe_camera_host(hass: HomeAssistant) -> None:
    """A camera host outside the private-LAN allowlist is rejected."""
    coordinator = _FakeCoordinator(hass)
    payload = {"user": "u", "password": "p", "urls": ["8.8.8.8:443"]}
    with patch(
        f"{_MOD}.async_bosch_cloud_session_cm",
        return_value=_session_cm(_put_cm(200, payload)),
    ):
        result = await async_start_local_stream(coordinator, CAM_ID, {}, {})
    assert result is None


async def test_success_builds_credential_embedded_rtsp_url(
    hass: HomeAssistant,
) -> None:
    """A healthy LOCAL session starts the TLS proxy and returns its RTSP URL."""
    coordinator = _FakeCoordinator(hass)
    payload = {"user": "us er", "password": "p@ss", "urls": ["192.168.1.50:443"]}
    port_cache: dict[str, int] = {}
    server_cache: dict[str, Any] = {}
    died_cb = MagicMock()
    with (
        patch(
            f"{_MOD}.async_bosch_cloud_session_cm",
            return_value=_session_cm(_put_cm(200, payload)),
        ),
        patch(f"{_MOD}.start_tls_proxy", AsyncMock(return_value=54321)) as mock_start,
    ):
        result = await async_start_local_stream(
            coordinator, CAM_ID, port_cache, server_cache, on_proxy_died=died_cb
        )

    assert result is not None
    assert result.startswith("rtsp://us%20er:p%40ss@127.0.0.1:54321/rtsp_tunnel")
    assert "inst=2" in result
    assert "enableaudio=1" in result
    assert "maxSessionDuration=3600" in result
    mock_start.assert_awaited_once()
    _, kwargs = mock_start.await_args
    assert kwargs["on_proxy_died"] is died_cb
    call_args = mock_start.await_args.args
    assert call_args[1] == CAM_ID
    assert call_args[2] == "192.168.1.50"
    assert call_args[3] == 443
    assert call_args[4] is port_cache
    assert call_args[5] is server_cache


async def test_async_stop_local_stream_delegates_to_library(
    hass: HomeAssistant,
) -> None:
    """async_stop_local_stream is a thin pass-through to the library's stop_tls_proxy."""
    port_cache: dict[str, int] = {CAM_ID: 1}
    server_cache: dict[str, Any] = {CAM_ID: MagicMock()}
    with patch(f"{_MOD}.stop_tls_proxy", AsyncMock()) as mock_stop:
        await async_stop_local_stream(CAM_ID, port_cache, server_cache)
    mock_stop.assert_awaited_once_with(CAM_ID, port_cache, server_cache)
