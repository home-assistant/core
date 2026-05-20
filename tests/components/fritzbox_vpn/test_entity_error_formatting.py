"""Tests for FritzBox VPN entity error formatting."""

from __future__ import annotations

import pytest

from homeassistant.components.fritzbox_vpn.entity import raise_toggle_failed
from homeassistant.exceptions import HomeAssistantError


def test_raise_toggle_failed_no_error_suffix() -> None:
    """Empty error placeholder should not produce an extra ': '."""
    with pytest.raises(HomeAssistantError) as exc_info:
        raise_toggle_failed("VPN-Name")

    err = exc_info.value
    assert err.translation_domain == "fritzbox_vpn"
    assert err.translation_key == "toggle_failed"
    assert err.translation_placeholders == {"name": "VPN-Name", "error": ""}


def test_raise_toggle_failed_formats_error_placeholder() -> None:
    """Non-empty error placeholder should be formatted with ': <error>'."""
    with pytest.raises(HomeAssistantError) as exc_info:
        raise_toggle_failed("VPN-Name", "boom")

    err = exc_info.value
    assert err.translation_placeholders == {"name": "VPN-Name", "error": ": boom"}
