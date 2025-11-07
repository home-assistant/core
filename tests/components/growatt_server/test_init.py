"""Tests for the Growatt Server integration."""

from datetime import timedelta
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import growattServer
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_device_info(
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (growattServer.GrowattV1ApiError("API Error"), ConfigEntryState.SETUP_ERROR),
        (
            json.decoder.JSONDecodeError("Invalid JSON", "", 0),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_error_on_api_failure(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup error on API failures during device list."""
    mock_growatt_v1_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles update failures gracefully."""
    # Integration should be loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Cause coordinator update to fail
    mock_growatt_v1_api.min_detail.side_effect = growattServer.GrowattV1ApiError(
        "Connection timeout"
    )

    # Trigger coordinator refresh
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Integration should remain loaded despite coordinator error
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_classic_api_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test integration setup with Classic API (password auth)."""
    # Classic API doesn't support MIN devices - use TLX device instead
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # Verify Classic API login was called
    mock_growatt_classic_api.login.assert_called()

    # Verify device was created
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "TLX123456")})
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_unload_removes_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unloading removes all listeners."""
    # Get initial listener count
    initial_listeners = len(hass.bus.async_listeners())

    # Unload the integration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify listeners were removed (should be same or less)
    final_listeners = len(hass.bus.async_listeners())
    assert final_listeners <= initial_listeners


async def test_multiple_devices_discovered(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling multiple devices from device_list."""
    # Reset and add multiple devices
    mock_config_entry_new = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        unique_id="plant_456",
    )

    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {"device_sn": "MIN123456", "type": 7},
            {"device_sn": "MIN789012", "type": 7},
        ]
    }

    with patch(
        "homeassistant.components.growatt_server.coordinator.SCAN_INTERVAL",
        timedelta(minutes=5),
    ):
        await setup_integration(hass, mock_config_entry_new)

    # Verify both devices were created
    device1 = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    device2 = device_registry.async_get_device(identifiers={(DOMAIN, "MIN789012")})

    assert device1 is not None
    assert device1 == snapshot(name="device_min123456")
    assert device2 is not None
    assert device2 == snapshot(name="device_min789012")


async def test_migrate_legacy_api_token_config(
    hass: HomeAssistant,
    mock_growatt_v1_api,
) -> None:
    """Test migration of legacy config entry with API token but no auth_type."""
    # Create a legacy config entry without CONF_AUTH_TYPE
    legacy_config = {
        CONF_TOKEN: "test_token_123",
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_123",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=legacy_config,
        unique_id="plant_123",
    )

    await setup_integration(hass, mock_config_entry)

    # Verify migration occurred and auth_type was added
    assert mock_config_entry.data[CONF_AUTH_TYPE] == AUTH_API_TOKEN
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_migrate_legacy_password_config(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test migration of legacy config entry with password auth but no auth_type."""
    # Create a legacy config entry without CONF_AUTH_TYPE
    legacy_config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
        CONF_URL: "https://server.growatt.com/",
        "plant_id": "plant_456",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=legacy_config,
        unique_id="plant_456",
    )

    # Classic API doesn't support MIN devices - use TLX device instead
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry)

    # Verify migration occurred and auth_type was added
    assert mock_config_entry.data[CONF_AUTH_TYPE] == AUTH_PASSWORD
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_migrate_legacy_config_no_auth_fields(
    hass: HomeAssistant,
) -> None:
    """Test that config entry with no recognizable auth fields raises error."""
    # Create a config entry without any auth fields
    invalid_config = {
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_789",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=invalid_config,
        unique_id="plant_789",
    )

    await setup_integration(hass, mock_config_entry)

    # The ConfigEntryError is caught by the config entry system
    # and the entry state is set to SETUP_ERROR
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
