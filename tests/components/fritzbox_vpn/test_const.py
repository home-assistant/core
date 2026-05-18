"""Tests for const helpers."""

from custom_components.fritzbox_vpn.const import (
    auth_error_notification_id,
    host_from_config,
    mask_config_for_log,
    password_from_sources,
)


def test_password_from_sources() -> None:
    """First non-empty password wins across dicts."""
    assert password_from_sources(None, {"password": "a"}, {"pass": "b"}) == "a"
    assert password_from_sources({"pass": "x"}) == "x"
    assert password_from_sources({}) == ""


def test_mask_config_for_log() -> None:
    """Sensitive keys are masked in log copies."""
    masked = mask_config_for_log(
        {"host": "1.2.3.4", "username": "u", "password": "secret"}
    )
    assert masked["password"] == "***"
    assert masked["host"] == "1.2.3.4"


def test_host_and_notification_id() -> None:
    """Host fallback and notification id formatting."""
    assert host_from_config({}) == "unknown"
    assert auth_error_notification_id("192.168.178.1").endswith("192.168.178.1")
