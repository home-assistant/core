"""Test the Teslemetry init."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
import time
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from bleak.exc import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import (
    BluetoothCommandFailed,
    BluetoothTransportError,
    BluetoothUnconfirmedCommand,
    Forbidden,
    InsufficientCredits,
    InvalidResponse,
    InvalidToken,
    LoginRequired,
    RateLimited,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tesla import VehicleRouter
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.teslemetry import _get_access_token
from homeassistant.components.teslemetry.const import (
    CLIENT_ID,
    CONF_VIN,
    DOMAIN,
    SUBENTRY_TYPE_VEHICLE,
)

# Coordinator constants
from homeassistant.components.teslemetry.coordinator import (
    ENERGY_HISTORY_INTERVAL,
    ENERGY_INFO_INTERVAL,
    ENERGY_LIVE_INTERVAL,
    INSUFFICIENT_CREDITS_RETRY_AFTER,
    METADATA_INTERVAL,
    VEHICLE_INTERVAL,
)
from homeassistant.components.teslemetry.helpers import async_get_ble_parent
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.components.teslemetry.oauth import TeslemetryImplementation
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import (
    CONF_ADDRESS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import mock_config_entry, setup_platform
from .const import (
    CONFIG_V1,
    ENERGY_HISTORY,
    LIVE_STATUS,
    METADATA,
    METADATA_NOSCOPE,
    PRODUCTS_MODERN,
    SITE_INFO,
    UNIQUE_ID,
    VEHICLE_DATA,
    VEHICLE_DATA_ALT,
    VEHICLE_DATA_ASLEEP,
)

from tests.common import MockConfigEntry, async_fire_time_changed

ERRORS = [
    (InvalidToken, ConfigEntryState.SETUP_ERROR),
    (LoginRequired, ConfigEntryState.SETUP_ERROR),
    (SubscriptionRequired, ConfigEntryState.SETUP_ERROR),
    (TeslaFleetError, ConfigEntryState.SETUP_RETRY),
]

VEHICLE_ERRORS = [
    *ERRORS,
    (InsufficientCredits, ConfigEntryState.SETUP_RETRY),
]


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, TeslemetryData)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(entry, "runtime_data")


@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_init_error(
    hass: HomeAssistant,
    mock_products: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
) -> None:
    """Test init with errors."""

    mock_products.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


# Test devices
async def test_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test device registry."""
    entry = await setup_platform(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    for device in devices:
        assert device == snapshot(name=f"{device.identifiers}")


@pytest.mark.parametrize(("side_effect", "state"), VEHICLE_ERRORS)
async def test_vehicle_refresh_error(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
    mock_legacy: AsyncMock,
) -> None:
    """Test coordinator refresh with an error."""
    mock_vehicle_data.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


# Test Energy Live Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_live_refresh_error(
    hass: HomeAssistant,
    mock_live_status: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
) -> None:
    """Test coordinator refresh with an error."""
    mock_live_status.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


# Test Energy Site Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_site_refresh_error(
    hass: HomeAssistant,
    mock_site_info: AsyncMock,
    side_effect: TeslaFleetError,
    state: ConfigEntryState,
) -> None:
    """Test coordinator refresh with an error."""
    mock_site_info.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_vehicle_stream(
    hass: HomeAssistant,
    mock_add_listener: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test vehicle stream events."""

    await setup_platform(hass, [Platform.BINARY_SENSOR])
    mock_add_listener.assert_called()

    state = hass.states.get("binary_sensor.test_status")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("binary_sensor.test_user_present")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "vehicle_data": VEHICLE_DATA_ALT["response"],
            "state": "online",
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_status")
    assert state is not None
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.test_user_present")
    assert state is not None
    assert state.state == STATE_ON

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "state": "offline",
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_status")
    assert state is not None
    assert state.state == STATE_OFF


async def test_vehicle_asleep_polling(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Polling an offline/asleep vehicle loads and reports disconnected."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ASLEEP
    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.test_status")
    assert state is not None
    assert state.state == STATE_OFF


async def test_no_live_status(
    hass: HomeAssistant,
    mock_live_status: AsyncMock,
) -> None:
    """Test coordinator refresh with an error."""
    mock_live_status.side_effect = AsyncMock({"response": ""})
    await setup_platform(hass)

    assert hass.states.get("sensor.energy_site_grid_power") is None


async def test_modern_no_poll(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_products: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that modern vehicles do not poll vehicle_data."""

    mock_products.return_value = PRODUCTS_MODERN
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert mock_vehicle_data.called is False
    freezer.tick(VEHICLE_INTERVAL)
    assert mock_vehicle_data.called is False
    freezer.tick(VEHICLE_INTERVAL)
    assert mock_vehicle_data.called is False


async def test_stale_device_removal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_products: AsyncMock,
) -> None:
    """Test removal of stale devices."""

    # Setup the entry first to get a valid config_entry_id
    entry = await setup_platform(hass)

    # Create a device that should be removed (with the valid entry_id)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "stale-vin")},
        manufacturer="Tesla",
        name="Stale Vehicle",
    )

    # Verify the stale device exists
    pre_devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    stale_identifiers = {
        identifier for device in pre_devices for identifier in device.identifiers
    }
    assert (DOMAIN, "stale-vin") in stale_identifiers

    # Update products with an empty response (no devices) and reload entry
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.products",
        return_value={"response": []},
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        # Get updated devices after reload
        post_devices = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )
        post_identifiers = {
            identifier for device in post_devices for identifier in device.identifiers
        }

        # Verify the stale device has been removed
        assert (DOMAIN, "stale-vin") not in post_identifiers

        # Verify the device itself has been completely removed from the registry
        # since it had no other config entries
        updated_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "stale-vin"), entry.entry_id
        )
        assert updated_device is None


async def test_skipped_energy_site_is_removed_as_stale_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test skipped energy sites do not block stale device removal."""
    entry = await setup_platform(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "98765")},
        manufacturer="Tesla",
        name="Skipped Energy Site",
    )

    refreshed_metadata = deepcopy(METADATA)
    refreshed_metadata["energy_sites"]["98765"] = {
        "access": True,
        "name": "Skipped Energy Site",
    }

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=refreshed_metadata,
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    updated_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "98765"), entry.entry_id
    )
    assert updated_device is None


async def test_device_retention_during_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_products: AsyncMock,
) -> None:
    """Test that valid devices are retained during a config entry reload."""
    # Setup entry with normal devices
    entry = await setup_platform(hass)

    # Get initial device count and identifiers
    pre_devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    pre_count = len(pre_devices)
    pre_identifiers = {
        identifier for device in pre_devices for identifier in device.identifiers
    }

    # Make sure we have some devices
    assert pre_count > 0

    # Save the original identifiers to compare after reload
    original_identifiers = pre_identifiers.copy()

    # Reload the config entry with the same products data
    # The mock_products fixture will return the same data as during setup
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Verify device count and identifiers after reload match pre-reload
    post_devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    post_count = len(post_devices)
    post_identifiers = {
        identifier for device in post_devices for identifier in device.identifiers
    }

    # Since the products data didn't change, we should have the same devices
    assert post_count == pre_count
    assert post_identifiers == original_identifiers


async def test_migrate_from_version_1_success(hass: HomeAssistant) -> None:
    """Test successful config migration from version 1."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=UNIQUE_ID,
        data=CONFIG_V1,
    )

    # Mock the migrate token endpoint response
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.migrate_to_oauth",
        new_callable=AsyncMock,
    ) as mock_migrate:
        mock_migrate.return_value = {
            "token": {
                "access_token": "migrated_token",
                "token_type": "Bearer",
                "refresh_token": "migrated_refresh_token",
                "expires_in": 3600,
                "expires_at": time.time() + 3600,
            }
        }

        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        mock_migrate.assert_called_once_with(CLIENT_ID, hass.config.location_name)

    assert mock_entry is not None
    assert mock_entry.version == 2
    # Verify data was converted to OAuth format
    assert "token" in mock_entry.data
    assert mock_entry.data["token"]["access_token"] == "migrated_token"
    assert mock_entry.data["token"]["refresh_token"] == "migrated_refresh_token"
    # Verify auth_implementation was added for OAuth2 flow compatibility
    assert mock_entry.data["auth_implementation"] == DOMAIN
    assert mock_entry.state is ConfigEntryState.LOADED


async def test_migrate_from_version_1_token_endpoint_error(hass: HomeAssistant) -> None:
    """Test config migration handles token endpoint errors."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=UNIQUE_ID,
        data=CONFIG_V1,
    )

    # Mock the migrate token endpoint to raise an HTTP error
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.migrate_to_oauth",
        new_callable=AsyncMock,
    ) as mock_migrate:
        mock_migrate.side_effect = ClientResponseError(
            request_info=MagicMock(), history=(), status=400
        )

        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        mock_migrate.assert_called_once_with(CLIENT_ID, hass.config.location_name)

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1  # Version should remain unchanged on migration failure


async def test_migrate_version_2_no_migration_needed(hass: HomeAssistant) -> None:
    """Test that version 2 entries don't need migration."""
    oauth_config = {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "existing_oauth_token",
            "token_type": "Bearer",
            "refresh_token": "existing_refresh_token",
            "expires_in": 3600,
            "expires_at": 1234567890,
        },
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,  # Already current version
        unique_id=UNIQUE_ID,
        data=oauth_config,
    )

    # Should not call the migrate endpoint since already version 2
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.migrate_to_oauth",
        new_callable=AsyncMock,
    ) as mock_migrate:
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        # Migration should not be called
        mock_migrate.assert_not_called()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry is not None
    assert entry.version == 2
    # Verify data was not modified
    assert entry.data == oauth_config
    assert entry.state is ConfigEntryState.LOADED


async def test_migrate_from_future_version_fails(hass: HomeAssistant) -> None:
    """Test migration fails for future versions."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,  # Future version
        unique_id=UNIQUE_ID,
        data={
            "token": {
                "access_token": "future_token",
                "token_type": "Bearer",
                "refresh_token": "future_refresh_token",
                "expires_in": 3600,
            }
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 3  # Version should remain unchanged


async def test_oauth_implementation_not_available(hass: HomeAssistant) -> None:
    """Test that missing OAuth implementation triggers reauth."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=UNIQUE_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    mock_entry.add_to_hass(hass)

    # Mock the implementation lookup to raise ValueError
    with patch(
        "homeassistant.components.teslemetry.async_get_config_entry_implementation",
        side_effect=ValueError("Implementation not available"),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry is not None
    # Should trigger reauth, not just fail silently
    assert entry.state is ConfigEntryState.SETUP_ERROR


RETRY_EXCEPTIONS = [
    (RateLimited(data={"after": 5}), 5.0),
    (InvalidResponse(), 10.0),
]


@pytest.mark.parametrize(("exception", "expected_retry_after"), RETRY_EXCEPTIONS)
async def test_site_info_retry_exceptions(
    hass: HomeAssistant,
    mock_site_info: AsyncMock,
    exception: TeslaFleetError,
    expected_retry_after: float,
) -> None:
    """Test UpdateFailed with retry_after for site info coordinator."""
    mock_site_info.side_effect = exception
    entry = await setup_platform(hass)
    # Retry exceptions during first refresh cause setup retry
    assert entry.state is ConfigEntryState.SETUP_RETRY
    # API should only be called once (no manual retries)
    assert mock_site_info.call_count == 1


@pytest.mark.parametrize(("exception", "expected_retry_after"), RETRY_EXCEPTIONS)
async def test_vehicle_data_retry_exceptions(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
    exception: TeslaFleetError,
    expected_retry_after: float,
) -> None:
    """Test UpdateFailed with retry_after for vehicle data coordinator."""
    mock_vehicle_data.side_effect = exception
    entry = await setup_platform(hass)
    # Retry exceptions during first refresh cause setup retry
    assert entry.state is ConfigEntryState.SETUP_RETRY
    # API should only be called once (no manual retries)
    assert mock_vehicle_data.call_count == 1


@pytest.mark.parametrize(("exception", "expected_retry_after"), RETRY_EXCEPTIONS)
async def test_live_status_coordinator_retry_exceptions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_live_status: AsyncMock,
    exception: TeslaFleetError,
    expected_retry_after: float,
) -> None:
    """Test live status coordinator raises UpdateFailed with retry_after."""
    call_count = 0

    def live_status_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return deepcopy(LIVE_STATUS)  # Initial call succeeds
        if call_count == 2:
            raise exception  # Second call raises exception
        return deepcopy(LIVE_STATUS)  # Subsequent calls succeed

    mock_live_status.side_effect = live_status_side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert call_count == 1

    # Trigger coordinator refresh - this will raise the exception
    freezer.tick(ENERGY_LIVE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # API was called exactly once for this refresh (no manual retry loop)
    assert call_count == 2
    # Entry stays loaded - UpdateFailed with retry_after doesn't break the entry
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("exception", "expected_retry_after"), RETRY_EXCEPTIONS)
async def test_energy_history_coordinator_retry_exceptions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    exception: TeslaFleetError,
    expected_retry_after: float,
) -> None:
    """Test energy history coordinator raises UpdateFailed with retry_after."""
    call_count = 0

    def energy_history_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise exception  # First call raises exception
        return ENERGY_HISTORY  # Subsequent calls succeed

    mock_energy_history.side_effect = energy_history_side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    # Energy history doesn't have first_refresh during setup
    assert call_count == 0

    # Trigger first coordinator refresh - this will raise the exception
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # API was called exactly once (no manual retry loop)
    assert call_count == 1
    # Entry stays loaded - UpdateFailed with retry_after doesn't break the entry
    assert entry.state is ConfigEntryState.LOADED


async def test_live_status_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test live status coordinator handles auth errors."""
    call_count = 0

    def live_status_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return deepcopy(LIVE_STATUS)
        raise InvalidToken

    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.live_status",
        side_effect=live_status_side_effect,
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.LOADED

        # Trigger a coordinator refresh by advancing time
        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Auth error triggers reauth flow
        assert entry.state is ConfigEntryState.LOADED


async def test_live_status_generic_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test live status coordinator handles generic TeslaFleetError."""
    call_count = 0

    def live_status_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return deepcopy(LIVE_STATUS)
        raise TeslaFleetError

    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.live_status",
        side_effect=live_status_side_effect,
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.LOADED

        # Trigger a coordinator refresh by advancing time
        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Entry stays loaded but coordinator will have failed
        assert entry.state is ConfigEntryState.LOADED


async def test_missing_token_data(hass: HomeAssistant) -> None:
    """Test that missing token data in config entry triggers auth failure."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=UNIQUE_ID,
        data={
            "auth_implementation": DOMAIN,
            # token is intentionally missing
        },
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_vehicle_streaming_version_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test vehicle sw_version is updated when streaming reports new version."""
    # Track listen_Version calls
    version_listeners: list = []

    def mock_listen_version(callback):
        version_listeners.append(callback)
        return lambda: None  # Return unsubscribe function

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_Version",
        side_effect=mock_listen_version,
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.LOADED

    # Check initial device sw_version
    vin = "LRW3F7EK4NC700000"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2026.0.0"

    # Simulate streaming version update
    assert len(version_listeners) > 0
    version_listeners[0]("2026.1.0 abc123")
    await hass.async_block_till_done()

    # Check device sw_version was updated (build hash removed)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2026.1.0"


async def test_vehicle_streaming_version_update_ignores_none(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test vehicle sw_version is not updated when streaming reports None."""
    version_listeners: list = []

    def mock_listen_version(callback):
        version_listeners.append(callback)
        return lambda: None

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_Version",
        side_effect=mock_listen_version,
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.LOADED

    vin = "LRW3F7EK4NC700000"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    original_version = device.sw_version

    # Simulate streaming version update with None
    assert len(version_listeners) > 0
    version_listeners[0](None)
    await hass.async_block_till_done()

    # Check device sw_version was not changed
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == original_version


async def test_vehicle_polling_version_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test vehicle sw_version updates when polling coordinator refreshes."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    vin = "LRW3F7EK4NC700000"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2026.0.0"

    # Update mock to return new version on next poll
    updated_vehicle_data = deepcopy(VEHICLE_DATA)
    updated_vehicle_data["response"]["vehicle_state"]["car_version"] = "2026.2.0 def456"
    mock_vehicle_data.return_value = updated_vehicle_data

    # Trigger coordinator refresh
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check device sw_version was updated (build hash removed)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2026.2.0"


async def test_energy_site_version_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_site_info: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test energy site sw_version updates when info coordinator refreshes."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    site_id = "123456"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, site_id), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "23.44.0 eb113390"

    # Update mock to return new version on next poll
    updated_site_info = deepcopy(SITE_INFO)
    updated_site_info["response"]["version"] = "24.1.0 abc123"
    mock_site_info.side_effect = lambda: updated_site_info

    # Trigger coordinator refresh
    freezer.tick(ENERGY_INFO_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check device sw_version was updated
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, site_id), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "24.1.0 abc123"


# Exception translation tests


async def test_live_status_auth_failed_forbidden(
    hass: HomeAssistant,
    mock_live_status: AsyncMock,
) -> None:
    """Test Forbidden exception during live_status triggers auth failure."""
    mock_live_status.side_effect = Forbidden
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "side_effect",
    [[deepcopy(LIVE_STATUS), TeslaFleetError]],
)
async def test_live_status_coordinator_refresh_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_live_status: AsyncMock,
    side_effect: list,
) -> None:
    """Test live status coordinator handles errors during refresh."""
    mock_live_status.side_effect = side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    freezer.tick(ENERGY_LIVE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        [InvalidToken],
        [TeslaFleetError],
        [ENERGY_HISTORY, {"response": {}}],
    ],
)
async def test_energy_history_coordinator_refresh_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    side_effect: list,
) -> None:
    """Test energy history coordinator handles errors during refresh."""
    mock_energy_history.side_effect = side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_dynamic_device_discovery_triggers_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that metadata coordinator triggers reload when new vehicle is added."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    # Update metadata to include a new vehicle with access
    new_metadata = deepcopy(METADATA)
    new_metadata["vehicles"]["5YJ3E1EA1NF000001"] = {
        "proxy": True,
        "access": True,
        "polling": False,
        "firmware": "2026.0.0",
    }

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=new_metadata,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        # Advance time to trigger metadata coordinator refresh
        freezer.tick(METADATA_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Verify reload was triggered due to new vehicle
    mock_reload.assert_called_once_with(entry.entry_id)


async def test_dynamic_device_discovery_no_reload_for_scope_only_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test metadata refresh does not reload when only scopes change."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=deepcopy(METADATA_NOSCOPE),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        freezer.tick(METADATA_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


async def test_dynamic_device_discovery_no_reload_without_changes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that metadata coordinator refresh without changes does not reload."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    # Patch to use the same metadata (no changes)
    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=deepcopy(METADATA),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        # Advance time to trigger metadata coordinator refresh
        freezer.tick(METADATA_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Verify reload was NOT triggered since no subscription changes
    mock_reload.assert_not_called()


async def test_insufficient_credits_backs_off_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Running out of command credits should back off, not hammer the API every poll."""
    call_count = 0

    def vehicle_data_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return deepcopy(VEHICLE_DATA)
        raise InsufficientCredits

    mock_vehicle_data.side_effect = vehicle_data_side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert call_count == 1

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert call_count == 2
    assert entry.state is ConfigEntryState.LOADED

    coordinator = entry.runtime_data.vehicles[0].coordinator
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.retry_after == INSUFFICIENT_CREDITS_RETRY_AFTER


def _oauth_session(hass: HomeAssistant, entry: MockConfigEntry) -> OAuth2Session:
    """Build an OAuth2Session for directly exercising _get_access_token."""
    return OAuth2Session(hass, entry, TeslemetryImplementation(hass, DOMAIN, CLIENT_ID))


async def test_get_access_token_dead_token_during_setup_triggers_auth_failed(
    hass: HomeAssistant,
) -> None:
    """A dead/revoked refresh token during setup must raise ConfigEntryAuthFailed.

    OAuth servers commonly report a dead refresh token with a non-401 status
    (e.g. 400 invalid_grant). Only recognizing status 401 let this fall
    through to ConfigEntryNotReady, which retries setup indefinitely without
    ever prompting the user to reauthenticate.
    """
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    mock_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    session = _oauth_session(hass, mock_entry)

    with (
        patch.object(
            OAuth2Session,
            "async_ensure_token_valid",
            side_effect=OAuth2TokenRequestReauthError(
                request_info=MagicMock(), status=400, domain=DOMAIN
            ),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await _get_access_token(session)


async def test_get_access_token_rate_limited_during_setup_is_not_fatal(
    hass: HomeAssistant,
) -> None:
    """A 429 from the token endpoint during setup should back off, not be fatal."""
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    mock_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    session = _oauth_session(hass, mock_entry)

    with (
        patch.object(
            OAuth2Session,
            "async_ensure_token_valid",
            side_effect=OAuth2TokenRequestTransientError(
                request_info=MagicMock(), status=429, domain=DOMAIN
            ),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await _get_access_token(session)


async def test_get_access_token_dead_token_after_setup_starts_reauth(
    hass: HomeAssistant,
) -> None:
    """Test a token dying after setup (re)starts reauth without tearing down.

    The coordinator handles the rest once the exception is re-raised.
    """
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    mock_entry.mock_state(hass, ConfigEntryState.LOADED)
    session = _oauth_session(hass, mock_entry)

    with (
        patch.object(
            OAuth2Session,
            "async_ensure_token_valid",
            side_effect=OAuth2TokenRequestReauthError(
                request_info=MagicMock(), status=400, domain=DOMAIN
            ),
        ),
        pytest.raises(OAuth2TokenRequestReauthError),
    ):
        await _get_access_token(session)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert any(
        flow["handler"] == DOMAIN and flow["context"].get("source") == "reauth"
        for flow in flows
    )


async def test_get_access_token_rate_limited_after_setup_is_not_fatal(
    hass: HomeAssistant,
) -> None:
    """A transient token-refresh error after setup must not force reauth."""
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    mock_entry.mock_state(hass, ConfigEntryState.LOADED)
    session = _oauth_session(hass, mock_entry)

    with (
        patch.object(
            OAuth2Session,
            "async_ensure_token_valid",
            side_effect=OAuth2TokenRequestTransientError(
                request_info=MagicMock(), status=429, domain=DOMAIN
            ),
        ),
        pytest.raises(OAuth2TokenRequestTransientError),
    ):
        await _get_access_token(session)
    await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress()


VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"
CLOUD_RESULT = {"response": {"result": True, "reason": "cloud"}}
BLE_RESULT = {"response": {"result": True, "reason": "bluetooth"}}


def _entry_with_ble() -> MockConfigEntry:
    """Return a config entry whose vehicle subentry is already BLE-paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=VIN,
                title="Test",
                data={CONF_VIN: VIN, CONF_ADDRESS: ADDRESS},
            )
        ],
    )


async def test_vehicle_router_with_bluetooth(hass: HomeAssistant) -> None:
    """A BLE-paired vehicle wraps its cloud API in a VehicleRouter."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert isinstance(vehicle.api, VehicleRouter)
    # Avoid replaying ambiguous commands or keeping the vehicle awake.
    mock_parent.return_value.vehicles.createBluetooth.assert_called_once_with(
        VIN,
        confirmation="verify",
        raise_unconfirmed=False,
        keepalive_interval=None,
    )


async def test_vehicle_cloud_without_bluetooth(hass: HomeAssistant) -> None:
    """A vehicle without a paired address keeps the plain cloud API."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert isinstance(vehicle.api, Vehicle)
    assert not isinstance(vehicle.api, VehicleRouter)


@asynccontextmanager
async def _paired_entry(
    hass: HomeAssistant, ble_lookup: MagicMock
) -> AsyncIterator[tuple[VehicleRouter, AsyncMock, AsyncMock]]:
    """Set up a BLE-paired entry, yielding its router and both backends."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()
    bluetooth_vehicle.set_device = MagicMock()

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            ble_lookup,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = (
            bluetooth_vehicle
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        router = entry.runtime_data.vehicles[0].api
        cloud = AsyncMock(return_value=CLOUD_RESULT)
        router.secondary.flash_lights = cloud
        yield router, bluetooth_vehicle, cloud


async def test_vehicle_bluetooth_out_of_range(hass: HomeAssistant) -> None:
    """A paired vehicle out of range still gets a router, and skips Bluetooth."""
    async with _paired_entry(hass, MagicMock(return_value=None)) as (
        router,
        bluetooth_vehicle,
        cloud,
    ):
        assert isinstance(router, VehicleRouter)

        assert await router.flash_lights() == CLOUD_RESULT

        cloud.assert_awaited_once()
        bluetooth_vehicle.flash_lights.assert_not_called()


async def test_vehicle_router_resumes_bluetooth_when_vehicle_returns(
    hass: HomeAssistant,
) -> None:
    """A vehicle away at setup routes locally again once it comes home."""
    ble_lookup = MagicMock(return_value=None)

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, cloud):
        bluetooth_vehicle.flash_lights.return_value = BLE_RESULT

        assert await router.flash_lights() == CLOUD_RESULT
        bluetooth_vehicle.flash_lights.assert_not_called()

        ble_lookup.return_value = MagicMock()

        assert await router.flash_lights() == BLE_RESULT
        bluetooth_vehicle.flash_lights.assert_awaited_once()
        cloud.assert_awaited_once()


async def test_vehicle_router_falls_back_when_vehicle_leaves(
    hass: HomeAssistant,
) -> None:
    """A vehicle in range at setup routes to cloud once it drives away."""
    ble_lookup = MagicMock(return_value=MagicMock())

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, cloud):
        bluetooth_vehicle.flash_lights.return_value = BLE_RESULT

        assert await router.flash_lights() == BLE_RESULT
        cloud.assert_not_called()

        ble_lookup.return_value = None

        assert await router.flash_lights() == CLOUD_RESULT
        cloud.assert_awaited_once()
        bluetooth_vehicle.flash_lights.assert_awaited_once()


async def test_vehicle_router_refreshes_device_handle(hass: HomeAssistant) -> None:
    """Each command refreshes the BLE handle from the cache before connecting."""
    first_device = MagicMock()
    second_device = MagicMock()
    ble_lookup = MagicMock(return_value=first_device)

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, _cloud):
        await router.flash_lights()
        bluetooth_vehicle.set_device.assert_called_once_with(first_device)

        ble_lookup.return_value = second_device
        await router.flash_lights()

        bluetooth_vehicle.set_device.assert_called_with(second_device)


async def test_vehicle_router_fails_over_on_stale_cache_hit(
    hass: HomeAssistant,
) -> None:
    """A cache entry outliving the vehicle costs one failed attempt, not a failure."""
    async with _paired_entry(hass, MagicMock(return_value=MagicMock())) as (
        router,
        bluetooth_vehicle,
        cloud,
    ):
        bluetooth_vehicle.flash_lights.side_effect = BluetoothTransportError()

        assert await router.flash_lights() == CLOUD_RESULT

        bluetooth_vehicle.flash_lights.assert_awaited_once()
        cloud.assert_awaited_once()


async def test_vehicle_paired_but_never_seen(hass: HomeAssistant) -> None:
    """A paired vehicle never seen by Bluetooth is built without a device handle."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            MagicMock(return_value=None),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        "device"
        not in mock_parent.return_value.vehicles.createBluetooth.call_args.kwargs
    )


@pytest.mark.parametrize(
    "disconnect_error",
    [None, BleakError("boom")],
    ids=["clean", "error_swallowed"],
)
async def test_unload_disconnects_bluetooth(
    hass: HomeAssistant, disconnect_error: Exception | None
) -> None:
    """Unloading a routed entry disconnects its Bluetooth backend, errors and all."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()
    bluetooth_vehicle.disconnect = AsyncMock(side_effect=disconnect_error)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = (
            bluetooth_vehicle
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert isinstance(entry.runtime_data.vehicles[0].api, VehicleRouter)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    bluetooth_vehicle.disconnect.assert_awaited_once()


async def test_unload_never_connected_bluetooth(hass: HomeAssistant) -> None:
    """Unloading a paired vehicle that was never in range does not raise."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = (
            bluetooth_vehicle
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    bluetooth_vehicle.disconnect.assert_awaited_once()


async def test_ble_parent_shared_and_cached(hass: HomeAssistant) -> None:
    """The BLE parent (holding the private key) is created once and reused."""
    with patch(
        "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
    ) as mock_parent:
        mock_parent.return_value.get_private_key = AsyncMock()
        first = await async_get_ble_parent(hass)
        second = await async_get_ble_parent(hass)

    assert first is second
    mock_parent.assert_called_once()
    mock_parent.return_value.get_private_key.assert_awaited_once()


async def test_ble_parent_concurrent_first_init(hass: HomeAssistant) -> None:
    """Concurrent first-time callers still create and load the key exactly once."""

    async def _get_private_key(path: str) -> None:
        await asyncio.sleep(0)

    with patch(
        "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
    ) as mock_parent:
        mock_parent.return_value.get_private_key = AsyncMock(
            side_effect=_get_private_key
        )
        parents = await asyncio.gather(*(async_get_ble_parent(hass) for _ in range(5)))

    assert all(parent is parents[0] for parent in parents)
    mock_parent.assert_called_once()
    mock_parent.return_value.get_private_key.assert_awaited_once()


async def test_router_does_not_fail_over_on_unconfirmed() -> None:
    """An unconfirmed BLE command is never replayed on the cloud backend."""
    bluetooth = AsyncMock()
    bluetooth.actuate_trunk = AsyncMock(side_effect=BluetoothUnconfirmedCommand())
    cloud = AsyncMock()
    cloud.actuate_trunk = AsyncMock(return_value={"response": {"result": True}})
    router = VehicleRouter(bluetooth, cloud)

    with pytest.raises(BluetoothUnconfirmedCommand):
        await router.actuate_trunk()

    cloud.actuate_trunk.assert_not_called()


async def test_router_fails_over_on_command_failed() -> None:
    """A command proven not to have applied over BLE fails over to the cloud."""
    bluetooth = AsyncMock()
    bluetooth.actuate_trunk = AsyncMock(side_effect=BluetoothCommandFailed())
    cloud = AsyncMock()
    cloud.actuate_trunk = AsyncMock(return_value={"response": {"result": True}})
    router = VehicleRouter(bluetooth, cloud)

    result = await router.actuate_trunk()

    assert result == {"response": {"result": True}}
    bluetooth.actuate_trunk.assert_awaited_once()
    cloud.actuate_trunk.assert_awaited_once()


async def _setup_paired_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose only account vehicle is already BLE-paired."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_subentry_removal_reloads(hass: HomeAssistant) -> None:
    """Removing a vehicle subentry reloads once; later updates do not re-schedule."""
    entry = await _setup_paired_entry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

        # A later entry update before the reload runs must not re-schedule it.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "marker": True}
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(entry.entry_id)


async def test_subentry_removal_keeps_vehicle_device_and_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing a vehicle subentry leaves the cloud vehicle device and entities intact."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VIN), entry.entry_id
    )
    assert device is not None
    # The device and its entities belong to the parent entry, never the subentry.
    assert device.config_subentry_id is None
    entities_before = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert entities_before
    assert all(entity.config_subentry_id is None for entity in entities_before)
    unique_ids_before = {entity.unique_id for entity in entities_before}

    # Patch the reload so only the subentry removal itself is exercised here.
    with patch.object(hass.config_entries, "async_schedule_reload"):
        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

    # The vehicle device and every entity on it survive the removal.
    device_after = device_registry.async_get_device_by_identifier(
        (DOMAIN, VIN), entry.entry_id
    )
    assert device_after is not None
    assert device_after.id == device.id
    entities_after = er.async_entries_for_device(
        entity_registry, device_after.id, include_disabled_entities=True
    )
    assert {entity.unique_id for entity in entities_after} == unique_ids_before


async def test_no_subentry_auto_created_at_setup(hass: HomeAssistant) -> None:
    """Setup never auto-creates a Bluetooth subentry for account vehicles."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)


async def test_user_subentry_persists_across_reload(hass: HomeAssistant) -> None:
    """A paired vehicle subentry survives a reload even if its vehicle leaves the account."""
    entry = await _setup_paired_entry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    # The vehicle drops off the account, so setup builds no vehicle for it, yet
    # the user-added subentry (with its stored credentials) must not be removed.
    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.products",
            return_value={"response": []},
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    assert subentries[0].subentry_id == subentry_id
    assert subentries[0].data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}
