"""Tests for the Growatt Server integration."""

from datetime import timedelta
import json

from freezegun.api import FrozenDateTimeFactory
import growattServer
import pytest
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server import get_device_list
from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
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


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (requests.exceptions.RequestException("Connection error"), None),
        (json.decoder.JSONDecodeError("Invalid JSON", "", 0), None),
        (None, {"success": False, "msg": "502"}),
        (None, {"success": False, "msg": "Server maintenance"}),
    ],
    ids=["network_error", "json_error", "invalid_auth", "other_login_error"],
)
async def test_classic_api_login_errors(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    side_effect: Exception | None,
    return_value: dict | None,
) -> None:
    """Test Classic API setup with various login errors."""
    if side_effect:
        mock_growatt_classic_api.login.side_effect = side_effect
    elif return_value:
        mock_growatt_classic_api.login.return_value = return_value

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (requests.exceptions.RequestException("Connection error"), None),
        (json.decoder.JSONDecodeError("Invalid JSON", "", 0), None),
        (None, {"data": []}),
    ],
    ids=["network_error", "json_error", "no_plants"],
)
async def test_classic_api_plant_list_errors(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    side_effect: Exception | None,
    return_value: dict | None,
) -> None:
    """Test Classic API setup with plant list errors (default plant_id path)."""
    # Create config entry with default plant ID to trigger plant_list call
    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
        CONF_URL: "https://server.growatt.com/",
        "plant_id": "0",  # DEFAULT_PLANT_ID
        CONF_AUTH_TYPE: AUTH_PASSWORD,
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_default",
    )

    # Login succeeds
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }

    # But plant_list fails
    if side_effect:
        mock_growatt_classic_api.plant_list.side_effect = side_effect
    elif return_value:
        mock_growatt_classic_api.plant_list.return_value = return_value

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_device_list_errors(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test Classic API setup with device list errors."""
    mock_growatt_classic_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_api_version(
    hass: HomeAssistant,
) -> None:
    """Test setup with unknown API version."""
    # Create a config entry with invalid auth type
    config = {
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_123",
        CONF_AUTH_TYPE: "unknown_auth",  # Invalid auth type
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_123",
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_classic_api_auto_select_plant(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test Classic API setup with default plant ID (auto-selects first plant)."""
    # Create config entry with default plant ID to trigger auto-selection
    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
        CONF_URL: "https://server.growatt.com/",
        "plant_id": "0",  # DEFAULT_PLANT_ID
        CONF_AUTH_TYPE: AUTH_PASSWORD,
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_auto",
    )

    # Login succeeds and plant_list returns a plant
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "AUTO_PLANT_123", "plantName": "Auto Plant"}]
    }
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX999999", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry)

    # Should be loaded successfully with auto-selected plant
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_v1_api_unsupported_device_type(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test V1 API logs warning for unsupported device types (non-MIN)."""
    config = {
        CONF_TOKEN: "test_token_123",
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_123",
        CONF_AUTH_TYPE: AUTH_API_TOKEN,
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_123",
    )

    # Return mix of MIN (type 7) and other device types
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {"device_sn": "MIN123456", "type": 7},  # Supported
            {"device_sn": "TLX789012", "type": 5},  # Unsupported
        ]
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Verify warning was logged for unsupported device
    assert "Device TLX789012 with type 5 not supported in Open API V1" in caplog.text


def test_get_device_list_unknown_api_version() -> None:
    """Test get_device_list raises error for unknown API version."""

    with pytest.raises(ConfigEntryError, match="Unknown API version: invalid"):
        get_device_list(None, {}, "invalid")
