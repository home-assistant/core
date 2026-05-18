"""Integration-style tests for FritzBoxVPNSession HTTP flows."""

from unittest.mock import AsyncMock, patch

import pytest
from fritzboxvpn import FritzBoxVPNSession

from tests.aiohttp_mock import MockAiohttpResponse, QueuedAiohttpSession, json_response
from tests.fixtures import (
    LOGIN_XML_CHALLENGE,
    LOGIN_XML_SID,
    MOCK_DATA_LUA_JSON,
    MOCK_HOST,
    MOCK_PASSWORD,
    MOCK_USERNAME,
)

LOGIN_XML_INVALID = (
    '<?xml version="1.0"?><SessionInfo><SID>0000000000000000</SID></SessionInfo>'
)

MOCK_DATA_VPN_OFF = {
    "data": {
        "init": {
            "boxConnections": {
                "conn-abc": {
                    "uid": "conn-abc",
                    "name": "Office VPN",
                    "active": 0,
                    "connected": 0,
                }
            }
        }
    }
}


def _login_sequence() -> list[MockAiohttpResponse]:
    """PBKDF2 probe (non-2$ challenge) + legacy MD5 GET/POST."""
    return [
        MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
        MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
        MockAiohttpResponse(200, text=LOGIN_XML_SID),
    ]


@pytest.mark.asyncio
async def test_session_reuses_cached_sid() -> None:
    """Cached SID skips further HTTP login calls."""
    session = QueuedAiohttpSession([])
    fb = FritzBoxVPNSession(session, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    fb.sid = "cached"
    client, sid = await fb.async_get_session()
    assert client is session
    assert sid == "cached"
    assert not session.requests


@pytest.mark.asyncio
async def test_session_md5_login_and_fetch_vpn() -> None:
    """Legacy MD5 login then data.lua fetch returns normalized VPN map."""
    http = QueuedAiohttpSession([*_login_sequence(), json_response(MOCK_DATA_LUA_JSON)])
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    connections = await fb.async_get_vpn_connections()
    assert "conn-abc" in connections
    assert connections["conn-abc"]["active"] is True


@pytest.mark.asyncio
async def test_session_invalid_sid_retry() -> None:
    """403 on data.lua invalidates session and retries once."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            MockAiohttpResponse(403, text="forbidden"),
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    connections = await fb.async_get_vpn_connections()
    assert "conn-abc" in connections


@pytest.mark.asyncio
async def test_session_login_invalid_sid_raises() -> None:
    """Login returning invalid SID value raises ValueError."""
    http = QueuedAiohttpSession(
        [
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_INVALID),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ValueError, match="Login failed"):
        await fb.async_get_session()


@pytest.mark.asyncio
async def test_session_html_response_raises() -> None:
    """Non-JSON data.lua response raises invalid SID error (after SID retry)."""
    html = MockAiohttpResponse(
        200,
        text="<html>login</html>",
        headers={"Content-Type": "text/html"},
    )
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            html,
            *_login_sequence(),
            html,
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ValueError, match="Invalid SID"):
        await fb.async_get_vpn_connections()


@pytest.mark.asyncio
async def test_session_https_fallback_on_status() -> None:
    """HTTPS 502 falls back to HTTP for login GET."""
    http = QueuedAiohttpSession(
        [
            MockAiohttpResponse(502, text="bad gateway"),
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_SID),
            json_response(MOCK_DATA_LUA_JSON),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    connections = await fb.async_get_vpn_connections()
    assert connections
    assert fb.protocol == "http"


@pytest.mark.asyncio
async def test_session_toggle_already_active() -> None:
    """Toggle to current state returns True without PUT."""
    http = QueuedAiohttpSession([*_login_sequence(), json_response(MOCK_DATA_LUA_JSON)])
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    assert await fb.async_toggle_vpn("conn-abc", True) is True
    assert not any(method == "PUT" for method, _, _ in http.requests)


@pytest.mark.asyncio
async def test_session_toggle_off_success() -> None:
    """Successful VPN deactivation verifies new state."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
            MockAiohttpResponse(200, text="ok"),
            json_response(MOCK_DATA_VPN_OFF),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with patch("fritzboxvpn.session.asyncio.sleep", new=AsyncMock()):
        assert await fb.async_toggle_vpn("conn-abc", False) is True


@pytest.mark.asyncio
async def test_session_toggle_unknown_connection() -> None:
    """Toggle returns False when connection UID is missing."""
    http = QueuedAiohttpSession([*_login_sequence(), json_response({"data": {"init": {}}})])
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    assert await fb.async_toggle_vpn("missing", True) is False


@pytest.mark.asyncio
async def test_session_toggle_put_forbidden_retry() -> None:
    """PUT 403 invalidates SID and retries toggle once."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
            MockAiohttpResponse(403, text="forbidden"),
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
            MockAiohttpResponse(200, text="ok"),
            json_response(MOCK_DATA_VPN_OFF),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with patch("fritzboxvpn.session.asyncio.sleep", new=AsyncMock()):
        assert await fb.async_toggle_vpn("conn-abc", False) is True


@pytest.mark.asyncio
async def test_session_invalidate_and_close() -> None:
    """invalidate_session and async_close clear SID."""
    fb = FritzBoxVPNSession(
        QueuedAiohttpSession([]), MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD
    )
    fb.sid = "x"
    fb.invalidate_session()
    assert fb.sid is None
    fb.sid = "y"
    await fb.async_close()
    assert fb.sid is None


@pytest.mark.asyncio
async def test_pbkdf2_login_when_supported() -> None:
    """PBKDF2 challenge format uses version=2 login."""
    challenge = (
        "2$5$0123456789abcdef0123456789abcdef"
        "$5$fedcba9876543210fedcba9876543210"
    )
    pbkdf2_challenge_xml = (
        f'<?xml version="1.0"?><SessionInfo><Challenge>{challenge}</Challenge></SessionInfo>'
    )
    http = QueuedAiohttpSession(
        [
            MockAiohttpResponse(200, text=pbkdf2_challenge_xml),
            MockAiohttpResponse(200, text=LOGIN_XML_SID),
            json_response(MOCK_DATA_LUA_JSON),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    connections = await fb.async_get_vpn_connections()
    assert "conn-abc" in connections
    assert any("version=2" in url for _, url, _ in http.requests)
