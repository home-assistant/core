"""Tests for the diagnostics data provided by the ESPHome integration."""

from typing import Any
from unittest.mock import ANY

from aioesphomeapi import APIClient
import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .common import MockDashboardRefresh
from .conftest import MockESPHomeDevice, MockESPHomeDeviceType

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


@pytest.mark.usefixtures("enable_bluetooth")
async def test_diagnostics_with_dashboard_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
    mock_client: APIClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry with dashboard data."""
    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
            "current_version": "2023.1.0",
        }
    )
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )
    await MockDashboardRefresh(hass).async_refresh()
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_device.entry
    )

    assert result == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


async def test_diagnostics_with_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice,
) -> None:
    """Test diagnostics for config entry with Bluetooth."""
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner is not None
    assert scanner.connectable is True
    entry = mock_bluetooth_entry_with_raw_adv.entry
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == {
        "dashboard": {
            "configured": False,
        },
        "bluetooth": {
            "available": True,
            "connections_free": 0,
            "connections_limit": 0,
            "scanner": {
                "connectable": True,
                "current_mode": None,
                "requested_mode": None,
                "discovered_device_timestamps": {},
                "discovered_devices_and_advertisement_data": [],
                "last_detection": ANY,
                "monotonic_time": ANY,
                "name": "test (AA:BB:CC:DD:EE:FC)",
                "scanning": True,
                "source": "AA:BB:CC:DD:EE:FC",
                "start_time": ANY,
                "time_since_last_device_detection": {},
                "type": "ESPHomeScanner",
            },
        },
        "config": {
            "created_at": ANY,
            "data": {
                "bluetooth_mac_address": "**REDACTED**",
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
            "subentries": [],
            "title": "Mock Title",
            "unique_id": "11:22:33:44:55:aa",
            "version": 1,
        },
        "storage_data": {
            "api_version": {"major": 99, "minor": 99},
            "device_info": {
                "bluetooth_mac_address": "**REDACTED**",
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
