"""Tests for FritzBox VPN coordinator parsing and login helpers."""

from custom_components.fritzbox_vpn.coordinator import _resolve_update_interval_seconds
from fritzboxvpn import FritzBoxVPNSession
from fritzboxvpn.parsing import (
    extract_box_connections_from_data,
    parse_blocktime_from_login_xml,
    parse_challenge_from_login_xml,
    parse_sid_from_login_response,
)

from tests.fixtures import LOGIN_XML_CHALLENGE, LOGIN_XML_SID, MOCK_DATA_LUA_JSON


def test_parse_login_xml() -> None:
    """Parse challenge, SID, and blocktime from login XML."""
    assert parse_challenge_from_login_xml(LOGIN_XML_CHALLENGE) == "12345"
    assert parse_sid_from_login_response(LOGIN_XML_SID) == "deadbeef"
    assert parse_blocktime_from_login_xml(LOGIN_XML_SID) is None


def test_extract_box_connections() -> None:
    """Extract boxConnections from data.lua JSON."""
    box = extract_box_connections_from_data(MOCK_DATA_LUA_JSON, "shareWireguard")
    assert box is not None
    assert "conn-abc" in box


def test_resolve_update_interval() -> None:
    """Resolve update interval from options and config."""
    assert _resolve_update_interval_seconds({}, {"update_interval": 120}) == 120
    assert _resolve_update_interval_seconds({"update_interval": 45}, None) == 45


def test_pbkdf2_response_format() -> None:
    """PBKDF2 response uses expected format for valid challenge."""
    challenge = "2$5$0123456789abcdef0123456789abcdef$5$fedcba9876543210fedcba9876543210"
    response = FritzBoxVPNSession._calculate_pbkdf2_response(challenge, "password")
    assert "$" in response
