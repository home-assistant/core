"""Tests for the Growatt Server integration."""

from datetime import timedelta
import json

from freezegun.api import FrozenDateTimeFactory
import growattServer
import pytest
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server import async_migrate_entry
from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CACHED_API_KEY,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
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


@pytest.mark.parametrize(
    ("config_data", "expected_auth_type"),
    [
        (
            {
                CONF_TOKEN: "test_token_123",
                CONF_URL: "https://openapi.growatt.com/",
                "plant_id": "plant_123",
            },
            AUTH_API_TOKEN,
        ),
        (
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_URL: "https://server.growatt.com/",
                "plant_id": "plant_456",
            },
            AUTH_PASSWORD,
        ),
    ],
)
async def test_migrate_config_without_auth_type(
    hass: HomeAssistant,
    config_data: dict[str, str],
    expected_auth_type: str,
) -> None:
    """Test migration adds auth_type field to legacy configs and bumps version.

    This test verifies that config entries created before auth_type was introduced
    are properly migrated by:
    - Adding CONF_AUTH_TYPE with the correct value (AUTH_API_TOKEN or AUTH_PASSWORD)
    - Bumping version from 1.0 to 1.1
    """
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        unique_id=config_data["plant_id"],
        version=1,
        minor_version=0,
    )

    mock_config_entry.add_to_hass(hass)

    # Execute migration
    migration_result = await async_migrate_entry(hass, mock_config_entry)
    assert migration_result is True

    # Verify version was updated to 1.1
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Verify auth_type field was added during migration
    assert mock_config_entry.data[CONF_AUTH_TYPE] == expected_auth_type


async def test_migrate_legacy_config_no_auth_fields(
    hass: HomeAssistant,
) -> None:
    """Test migration succeeds but setup fails for config without auth fields."""
    # Create a config entry without any auth fields
    invalid_config = {
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_789",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=invalid_config,
        unique_id="plant_789",
        version=1,
        minor_version=0,
    )

    mock_config_entry.add_to_hass(hass)

    # Migration should succeed (only updates version)
    migration_result = await async_migrate_entry(hass, mock_config_entry)
    assert migration_result is True

    # Verify version was updated
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Note: Setup will fail later due to missing auth fields in async_setup_entry


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_login_exceptions(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test Classic API setup with login exceptions."""
    mock_growatt_classic_api.login.side_effect = exception

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "login_response",
    [
        {"success": False, "msg": "502"},
        {"success": False, "msg": "Server maintenance"},
    ],
    ids=["invalid_auth", "other_login_error"],
)
async def test_classic_api_login_failures(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    login_response: dict,
) -> None:
    """Test Classic API setup with login failures."""
    mock_growatt_classic_api.login.return_value = login_response

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_device_list_exceptions(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    exception: Exception,
) -> None:
    """Test Classic API setup with device_list exceptions."""
    # Create a config entry that won't trigger migration
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_123",  # Specific ID to avoid migration
        },
        unique_id="plant_123",
    )

    # device_list raises exception during setup
    mock_growatt_classic_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_classic_api_device_list_no_devices(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test Classic API setup when device list returns no devices."""
    # Create a config entry that won't trigger migration
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_456",  # Specific ID to avoid migration
        },
        unique_id="plant_456",
    )

    # device_list returns empty list (no devices)
    mock_growatt_classic_api.device_list.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Should still load successfully even with no devices
    assert mock_config_entry.state is ConfigEntryState.LOADED


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
    mock_config_entry_classic_default_plant: MockConfigEntry,
) -> None:
    """Test Classic API setup with default plant ID (auto-selects first plant)."""
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

    await setup_integration(hass, mock_config_entry_classic_default_plant)

    # Should be loaded successfully with auto-selected plant
    assert mock_config_entry_classic_default_plant.state is ConfigEntryState.LOADED


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


async def test_migrate_version_bump(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test migration from 1.0 to 1.1 resolves DEFAULT_PLANT_ID and bumps version.

    This test verifies that:
    - Migration successfully resolves DEFAULT_PLANT_ID ("0") to actual plant_id
    - Config entry version is bumped from 1.0 to 1.1
    - API instance is cached for setup to reuse (rate limit optimization)
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    # Mock successful API responses for migration
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "RESOLVED_PLANT_789", "plantName": "My Plant"}]
    }

    mock_config_entry.add_to_hass(hass)

    # Execute migration
    migration_result = await async_migrate_entry(hass, mock_config_entry)
    assert migration_result is True

    # Verify version was updated to 1.1
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Verify plant_id was resolved to actual plant_id (not DEFAULT_PLANT_ID)
    assert mock_config_entry.data[CONF_PLANT_ID] == "RESOLVED_PLANT_789"

    # Verify API instance was cached for setup to reuse
    assert f"{CACHED_API_KEY}{mock_config_entry.entry_id}" in hass.data[DOMAIN]


async def test_setup_reuses_cached_api_from_migration(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setup reuses cached API instance from migration.

    This test verifies the rate limit optimization where:
    1. Migration calls login() and caches the authenticated API instance
    2. Setup retrieves and reuses the cached API (avoiding a second login())
    3. The cached API is removed after use (one-time use pattern)

    Without this caching, we would call login() twice within seconds:
        Migration: login() → plant_list()
        Setup:     login() → device_list()
    This would trigger Growatt API rate limiting (5-minute window per endpoint).

    With caching, we only call login() once:
        Migration: login() → plant_list() → [cache API]
        Setup:     [reuse API] → device_list()
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    # Mock successful API responses
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "RESOLVED_PLANT_789", "plantName": "My Plant"}]
    }
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    mock_growatt_classic_api.plant_info.return_value = {
        "deviceList": [],
        "totalEnergy": 1250.0,
        "todayEnergy": 12.5,
        "invTodayPpv": 2500,
        "plantMoneyText": "123.45/USD",
    }
    mock_growatt_classic_api.tlx_detail.return_value = {
        "data": {"deviceSn": "TLX123456"}
    }

    mock_config_entry.add_to_hass(hass)

    # Run migration first (resolves plant_id and caches authenticated API)
    await async_migrate_entry(hass, mock_config_entry)

    # Verify migration successfully resolved plant_id
    assert mock_config_entry.data[CONF_PLANT_ID] == "RESOLVED_PLANT_789"

    # Now setup the integration (should reuse cached API from migration)
    await setup_integration(hass, mock_config_entry)

    # Verify integration loaded successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify log message confirms API reuse (rate limit optimization)
    assert "Reusing logged-in session from migration" in caplog.text

    # Verify login was called with correct credentials
    # Note: Coordinators also call login() during refresh, so we verify
    # the call was made but don't assert it was called exactly once
    mock_growatt_classic_api.login.assert_called_with("test_user", "test_password")

    # Verify plant_list was called only once (during migration, not during setup)
    # This confirms setup did NOT resolve plant_id again (optimization working)
    mock_growatt_classic_api.plant_list.assert_called_once_with(123456)

    # Verify the cached API was removed after use (should not be in hass.data anymore)
    assert f"{CACHED_API_KEY}{mock_config_entry.entry_id}" not in hass.data.get(
        DOMAIN, {}
    )


async def test_migrate_failure_returns_false(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration returns False on API failure to allow retry.

    When migration fails due to API errors (network issues, etc.),
    it should return False and NOT bump the version. This allows Home Assistant
    to retry the migration on the next restart.
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    # Mock API failure (e.g., network error during login)
    mock_growatt_classic_api.login.side_effect = requests.exceptions.RequestException(
        "Network error"
    )

    mock_config_entry.add_to_hass(hass)

    # Execute migration (should fail gracefully)
    migration_result = await async_migrate_entry(hass, mock_config_entry)

    # Verify migration returned False (will retry on next restart)
    assert migration_result is False

    # Verify version was NOT bumped (remains 1.0)
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 0

    # Verify plant_id was NOT changed (remains DEFAULT_PLANT_ID)
    assert mock_config_entry.data[CONF_PLANT_ID] == DEFAULT_PLANT_ID

    # Verify error was logged
    assert "Failed to resolve plant_id during migration" in caplog.text
    assert "Migration will retry on next restart" in caplog.text


async def test_migrate_already_migrated(
    hass: HomeAssistant,
) -> None:
    """Test migration is skipped for already migrated entries."""
    # Create a config entry already at version 1.1
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_123",
        },
        unique_id="plant_specific",
        version=1,
        minor_version=1,
    )

    mock_config_entry.add_to_hass(hass)

    # Call migration function
    migration_result = await async_migrate_entry(hass, mock_config_entry)
    assert migration_result is True

    # Verify version remains 1.1 (no change)
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Plant ID should remain unchanged
    assert mock_config_entry.data[CONF_PLANT_ID] == "specific_plant_123"
