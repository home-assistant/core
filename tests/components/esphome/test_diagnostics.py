"""Tests for the diagnostics data provided by the ESPHome integration."""

from typing import Any
from unittest.mock import ANY

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("enable_bluetooth")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_dashboard: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result == snapshot(exclude=props("created_at", "modified_at"))


async def test_diagnostics_with_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice,
) -> None:
    """Test diagnostics for config entry with Bluetooth."""
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner is not None
    assert scanner.connectable is True
    entry = mock_bluetooth_entry_with_raw_adv.entry
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == {
        "bluetooth": {
            "available": True,
            "connections_free": 0,
            "connections_limit": 0,
            "scanner": {
                "connectable": True,
                "discovered_device_timestamps": {},
                "discovered_devices_and_advertisement_data": [],
                "last_detection": ANY,
                "monotonic_time": ANY,
                "name": "test (11:22:33:44:55:AA)",
                "scanning": True,
                "source": "11:22:33:44:55:AA",
                "start_time": ANY,
                "time_since_last_device_detection": {},
                "type": "ESPHomeScanner",
            },
        },
        "config": {
            "created_at": ANY,
            "data": {
                "device_name": "test",
                "host": "test.local",
                "password": "",
                "port": 6053,
            },
            "disabled_by": None,
            "discovery_keys": {},
            "domain": "esphome",
            "entry_id": ANY,
            "minor_version": 1,
            "modified_at": ANY,
            "options": {"allow_service_calls": False},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "title": "Mock Title",
            "unique_id": "11:22:33:44:55:aa",
            "version": 1,
        },
        "storage_data": {
            "api_version": {"major": 99, "minor": 99},
            "device_info": {
                "bluetooth_proxy_feature_flags": 63,
                "compilation_time": "",
                "esphome_version": "1.0.0",
                "friendly_name": "Test",
                "has_deep_sleep": False,
                "legacy_bluetooth_proxy_version": 0,
                "mac_address": "**REDACTED**",
                "manufacturer": "",
                "model": "",
                "name": "test",
                "project_name": "",
                "project_version": "",
                "suggested_area": "",
                "uses_password": False,
                "legacy_voice_assistant_version": 0,
                "voice_assistant_feature_flags": 0,
                "webserver_port": 0,
            },
            "services": [],
        },
    }
