"""Tests for Eufy RoboVac cloud API helpers."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.eufy_robovac.cloud_api import (
    CloudDiscoveredRoboVac,
    EufyRoboVacCloudApi,
)


def _vacuum(*, device_id: str, host: str) -> CloudDiscoveredRoboVac:
    return CloudDiscoveredRoboVac(
        device_id=device_id,
        model="T2253",
        name="RoboVac",
        local_key="abcdefghijklmnop",
        host=host,
        mac="AA:BB:CC:DD:EE:FF",
        description="RoboVac",
        protocol_version="3.3",
    )


def test_apply_local_host_fallback_backfills_missing_host() -> None:
    """Fallback scan should fill host when cloud response omits it."""
    api = EufyRoboVacCloudApi(username="user@example.com", password="password")
    discovered = [_vacuum(device_id="abc123", host="")]

    with patch.object(
        EufyRoboVacCloudApi,
        "_resolve_hosts_from_tinytuya_scan",
        return_value={"abc123": "192.168.1.55"},
    ):
        resolved = api._apply_local_host_fallback(discovered)

    assert resolved[0].host == "192.168.1.55"


def test_apply_local_host_fallback_keeps_existing_host() -> None:
    """Fallback scan should not replace host already provided by cloud."""
    api = EufyRoboVacCloudApi(username="user@example.com", password="password")
    discovered = [_vacuum(device_id="abc123", host="192.168.1.10")]

    with patch.object(
        EufyRoboVacCloudApi,
        "_resolve_hosts_from_tinytuya_scan",
        return_value={"abc123": "192.168.1.55"},
    ):
        resolved = api._apply_local_host_fallback(discovered)

    assert resolved[0].host == "192.168.1.10"


def test_apply_local_host_fallback_no_resolution_leaves_host_empty() -> None:
    """Fallback scan should leave host blank when device is not discovered locally."""
    api = EufyRoboVacCloudApi(username="user@example.com", password="password")
    discovered = [_vacuum(device_id="abc123", host="")]

    with patch.object(
        EufyRoboVacCloudApi,
        "_resolve_hosts_from_tinytuya_scan",
        return_value={},
    ):
        resolved = api._apply_local_host_fallback(discovered)

    assert resolved[0].host == ""
