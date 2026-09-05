"""Test the Teslemetry init."""

from copy import deepcopy
from datetime import timedelta
import logging
import time
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from aiopowerwall import PowerwallError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import (
    Forbidden,
    InsufficientCredits,
    InvalidResponse,
    InvalidToken,
    LoginRequired,
    RateLimited,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite

from homeassistant.components.teslemetry import (
    STREAM_TOPICS,
    _async_get_rsa_key_pem,
    _get_access_token,
)
from homeassistant.components.teslemetry.const import (
    CLIENT_ID,
    CONF_SITE_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENERGY_SITE,
)

# Coordinator constants
from homeassistant.components.teslemetry.coordinator import (
    ENERGY_CONFIG_INTERVAL,
    ENERGY_HISTORY_INTERVAL,
    ENERGY_LIVE_INTERVAL,
    INSUFFICIENT_CREDITS_RETRY_AFTER,
    METADATA_INTERVAL,
    VEHICLE_INTERVAL,
)
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.components.teslemetry.oauth import TeslemetryImplementation
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
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
    PRODUCTS,
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
    mock_add_listener: MagicMock,
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

    # The recovery/manual REST path still raises the exception
    await entry.runtime_data.energysites[0].live_coordinator.async_refresh()
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

        # The recovery/manual REST path surfaces the auth error
        await entry.runtime_data.energysites[0].live_coordinator.async_refresh()
        await hass.async_block_till_done()

        # Auth error triggers reauth flow
        assert entry.state is ConfigEntryState.LOADED


async def test_live_status_generic_error(
    hass: HomeAssistant,
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

        # The recovery/manual REST path surfaces the error
        await entry.runtime_data.energysites[0].live_coordinator.async_refresh()
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


@pytest.mark.parametrize(
    ("keep_one_enabled", "expected_polled"),
    [
        (False, False),
        (True, True),
    ],
    ids=["all_disabled", "one_enabled"],
)
async def test_vehicle_polling_stops_when_all_entities_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    keep_one_enabled: bool,
    expected_polled: bool,
) -> None:
    """Test the vehicle coordinator stops polling once every entity is disabled.

    With no listeners left, core unschedules the coordinator so the charged
    vehicle_data poll stops entirely; a single enabled entity keeps it running.
    """
    vin = "LRW3F7EK4NC700000"
    entry = await setup_platform(hass, [Platform.SENSOR])

    vehicle_entities = [
        entity
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.unique_id.startswith(vin)
    ]
    keep = {vehicle_entities[0].unique_id} if keep_one_enabled else set()
    for entity in vehicle_entities:
        if entity.unique_id not in keep:
            entity_registry.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )

    # Flush the debounced reload that disabling entities schedules.
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A scheduled poll only fires while the coordinator still has a listener.
    mock_vehicle_data.reset_mock()
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (mock_vehicle_data.call_count > 0) is expected_polled


async def test_energy_site_version_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_add_listener: MagicMock,
) -> None:
    """Test energy site sw_version updates from a site_info stream event."""
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    site_id = "123456"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, site_id), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "23.44.0 eb113390"

    # A slim site_info stream event carries the new version
    updated_site_info = deepcopy(SITE_INFO["response"])
    updated_site_info.pop("tariff_content_v2", None)
    updated_site_info["version"] = "24.1.0 abc123"
    mock_add_listener.send({"site_id": site_id, "site_info": updated_site_info})
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
    mock_live_status: AsyncMock,
    side_effect: list,
) -> None:
    """Test live status coordinator handles errors during refresh."""
    mock_live_status.side_effect = side_effect

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    await entry.runtime_data.energysites[0].live_coordinator.async_refresh()
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


SITE_ID = 123456
HOST = "192.168.91.1"
PASSWORD = "abcde"

# aiopowerwall's PowerwallClient parses the PEM at construction time, so tests
# that build one need a real (if undersized, for speed) RSA key rather than
# arbitrary bytes.
_TEST_RSA_KEY_PEM = rsa.generate_private_key(
    public_exponent=65537, key_size=1024
).private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)


def _entry_with_powerwall() -> MockConfigEntry:
    """Return a config entry whose energy site subentry is already paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={
                    CONF_SITE_ID: SITE_ID,
                    CONF_HOST: HOST,
                    CONF_PASSWORD: PASSWORD,
                },
            )
        ],
    )


async def _setup_account_no_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an account entry with no local-control subentry (nothing opted in)."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_energy_site_router_with_powerwall(hass: HomeAssistant) -> None:
    """A paired energy site wraps its cloud API in an EnergySiteRouter."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    energysite = entry.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySiteRouter)


async def test_energy_site_cloud_without_powerwall(hass: HomeAssistant) -> None:
    """An energy site without paired credentials keeps the plain cloud API."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    energysite = entry.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySite)
    assert not isinstance(energysite.api, EnergySiteRouter)


async def test_energy_site_subentry_without_credentials_uses_cloud(
    hass: HomeAssistant,
) -> None:
    """A subentry that exists but is not yet paired resolves to the cloud API.

    A site whose subentry was created but has no gateway host/password stored
    keeps that subentry_id (so it stays opted in) while falling back to the
    plain cloud API rather than building an EnergySiteRouter.
    """
    entry = mock_config_entry()
    paired = MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={CONF_SITE_ID: SITE_ID},
            )
        ],
    )
    paired.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(paired.entry_id)
        await hass.async_block_till_done()

    energysite = paired.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySite)
    assert not isinstance(energysite.api, EnergySiteRouter)
    assert energysite.subentry_id is not None
    assert energysite.can_local_control


async def test_no_subentry_created_at_setup(hass: HomeAssistant) -> None:
    """Setup never auto-creates a local-control subentry; it is opt-in."""
    entry = await _setup_account_no_subentry(hass)

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)
    energysite = entry.runtime_data.energysites[0]
    assert energysite.can_local_control
    assert energysite.subentry_id is None
    assert not isinstance(energysite.api, EnergySiteRouter)


@pytest.mark.parametrize(
    "local_error",
    [
        pytest.param(OSError("disk gone"), id="os_error"),
        pytest.param(ValueError("bad key"), id="value_error"),
        pytest.param(PowerwallError("client boom"), id="powerwall_error"),
    ],
)
async def test_local_control_failure_falls_back_to_cloud(
    hass: HomeAssistant,
    local_error: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure resolving a paired site's local gateway falls back to cloud.

    Local control is opt-in per site, so one site's bad local config must leave
    the entry loaded with cloud functionality intact rather than tearing the
    whole integration down.
    """
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            side_effect=local_error,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
        caplog.at_level(logging.WARNING),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    energysite = entry.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySite)
    assert not isinstance(energysite.api, EnergySiteRouter)
    assert energysite.can_local_control
    assert "falling back to cloud control" in caplog.text
    assert any(
        record.levelname == "WARNING" and str(SITE_ID) in record.message
        for record in caplog.records
    )


async def test_get_rsa_key_pem_generates_and_caches(hass: HomeAssistant) -> None:
    """The RSA key is generated/read once, then served from the hass.data cache."""
    with (
        patch(
            "homeassistant.components.teslemetry.Teslemetry.get_rsa_private_key",
            new=AsyncMock(),
        ) as mock_get_key,
        patch(
            "homeassistant.components.teslemetry.Path.read_bytes",
            return_value=_TEST_RSA_KEY_PEM,
        ),
    ):
        first = await _async_get_rsa_key_pem(hass)
        second = await _async_get_rsa_key_pem(hass)

    assert first == _TEST_RSA_KEY_PEM
    assert second == _TEST_RSA_KEY_PEM
    mock_get_key.assert_awaited_once()


@pytest.mark.parametrize(
    ("local_error", "expected", "cloud_awaits"),
    [
        pytest.param(None, {"routed": "local"}, 0, id="local_success"),
        pytest.param(
            PowerwallError("boom"), {"routed": "cloud"}, 1, id="cloud_fallback"
        ),
    ],
)
async def test_energy_site_router_command_routing(
    hass: HomeAssistant,
    local_error: Exception | None,
    expected: dict[str, str],
    cloud_awaits: int,
) -> None:
    """A command routes to the local Powerwall first and falls back to cloud."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    router = entry.runtime_data.energysites[0].api
    assert isinstance(router, EnergySiteRouter)

    local = AsyncMock(side_effect=local_error, return_value={"routed": "local"})
    cloud = AsyncMock(return_value={"routed": "cloud"})
    with (
        patch("aiopowerwall.energysite.PowerwallEnergySite.backup", new=local),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.backup",
            new=cloud,
        ),
    ):
        result = await router.backup(50)

    assert result == expected
    local.assert_awaited_once_with(50)
    assert cloud.await_count == cloud_awaits


async def test_stale_cleanup_preserves_foreign_subentry(hass: HomeAssistant) -> None:
    """Energy stale-subentry cleanup does not remove other subentry types."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    foreign = ConfigSubentry(
        data=MappingProxyType({"vin": "VIN123"}),
        subentry_type="vehicle",
        title="A Vehicle",
        unique_id="VIN123",
    )
    hass.config_entries.async_add_subentry(entry, foreign)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert foreign.subentry_id in entry.subentries
    assert entry.subentries[foreign.subentry_id].subentry_type == "vehicle"


async def test_stale_cleanup_removes_energy_subentry(hass: HomeAssistant) -> None:
    """A paired site that is gone from the account has its subentry pruned."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    products = deepcopy(PRODUCTS)
    products["response"] = [
        product
        for product in products["response"]
        if product.get("energy_site_id") != SITE_ID
    ]

    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert subentry_id not in entry.subentries


async def test_stale_cleanup_preserves_pairing_on_transient_access_loss(
    hass: HomeAssistant,
) -> None:
    """A paired site that momentarily reports no access keeps its subentry."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    metadata = deepcopy(METADATA)
    metadata["energy_sites"][str(SITE_ID)]["access"] = False

    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=metadata),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert subentry_id in entry.subentries
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == PASSWORD


async def test_solar_only_site_has_no_local_control(hass: HomeAssistant) -> None:
    """A solar-only site gets no local-control subentry: there is no Powerwall."""
    products = deepcopy(PRODUCTS)
    site = next(
        product
        for product in products["response"]
        if product.get("energy_site_id") == SITE_ID
    )
    site["components"]["battery"] = False
    site["components"].pop("wall_connectors")

    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)
    energysite = entry.runtime_data.energysites[0]
    assert energysite.subentry_id is None
    assert not isinstance(energysite.api, EnergySiteRouter)


async def test_stale_cleanup_preserves_pairing_without_energy_scope(
    hass: HomeAssistant,
) -> None:
    """Losing the energy scope must not delete a paired site's stored credentials."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=METADATA_NOSCOPE,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.runtime_data.energysites
    assert subentry_id in entry.subentries
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == PASSWORD


async def test_update_listener_ignores_token_refresh(hass: HomeAssistant) -> None:
    """An entry update that only changes token data must not reload the entry.

    OAuth token refreshes call async_update_entry with new token data on every
    expiry; reloading on those would needlessly drop the stream and re-fetch.
    """
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        new_data = dict(entry.data)
        new_data["token"] = {**new_data["token"], "access_token": "refreshed_token"}
        hass.config_entries.async_update_entry(entry, data=new_data)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


async def test_update_listener_reloads_on_subentry_change(
    hass: HomeAssistant,
) -> None:
    """Adding a local-energy-site subentry reloads the entry."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {CONF_SITE_ID: SITE_ID, CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
                ),
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                title="Energy Site",
                unique_id=str(SITE_ID),
            ),
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(entry.entry_id)


def test_stream_topic_allowlist() -> None:
    """The stream subscribes to exactly the topics the integration consumes."""
    assert [topic.value for topic in STREAM_TOPICS] == [
        "state",
        "vehicle_data",
        "data",
        "connectivity",
        "credits",
        "live_status",
        "site_info",
        "tariff_content_v2",
    ]


async def test_energy_stream_no_recurring_rest_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_live_status: AsyncMock,
    mock_site_info: AsyncMock,
) -> None:
    """The live/info REST cold reads happen once and do not recur."""
    await setup_platform(hass, [Platform.SENSOR])
    assert mock_live_status.call_count == 1
    assert mock_site_info.call_count == 1

    # Advancing well past the old 30-second poll intervals triggers no REST reads.
    freezer.tick(ENERGY_HISTORY_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_live_status.call_count == 1
    assert mock_site_info.call_count == 1


async def test_energy_stream_unload_unsubscribes_and_closes_stream(
    hass: HomeAssistant,
) -> None:
    """Unload runs each listener unsubscribe and closes the shared stream."""
    live_unsub = MagicMock()
    info_unsub = MagicMock()
    tariff_unsub = MagicMock()

    with (
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_LiveStatus",
            return_value=live_unsub,
        ),
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_SiteInfo",
            return_value=info_unsub,
        ),
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_TariffContentV2",
            return_value=tariff_unsub,
        ),
        patch("teslemetry_stream.TeslemetryStream.close") as mock_close,
    ):
        entry = await setup_platform(hass, [Platform.SENSOR])
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    live_unsub.assert_called_once()
    info_unsub.assert_called_once()
    tariff_unsub.assert_called_once()
    mock_close.assert_called_once()


async def test_energy_stream_disconnect_marks_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_add_connection_listener: MagicMock,
    mock_energy_live_stream: MagicMock,
    mock_energy_info_stream: MagicMock,
) -> None:
    """A dropped stream marks energy entities unavailable until documents resume."""
    await setup_platform(hass, [Platform.SENSOR, Platform.CALENDAR])

    # Both stream-driven coordinators start available from the setup cold read.
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE

    # A stream disconnect fails the live and info/tariff coordinators.
    mock_add_connection_listener.send(False)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == STATE_UNAVAILABLE
    assert hass.states.get("calendar.energy_site_buy_tariff").state == STATE_UNAVAILABLE

    # A streamed live_status document restores the live coordinator on reconnect.
    live_status = deepcopy(LIVE_STATUS["response"])
    live_status["solar_power"] = 456
    mock_energy_live_stream.send(live_status)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.energy_site_solar_power").state == "0.456"

    # A streamed site_info document restores the info/tariff coordinator.
    slim_site_info = {
        key: value
        for key, value in deepcopy(SITE_INFO["response"]).items()
        if key != "tariff_content_v2"
    }
    mock_energy_info_stream.send(slim_site_info)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE

    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN
    ]


# A paired site's LAN gateway returns a cloud-shaped live_status with distinct
# values for the ten locally-owned keys (grid_status "Inactive" and
# island_status "off_grid" differ from the cloud fixture so a reroute is
# visible) and None for the six keys it cannot serve.
_LOCAL_LIVE_STATUS = {
    "response": {
        "solar_power": 2000,
        "energy_left": 20000,
        "total_pack_energy": 40000,
        "percentage_charged": 80.0,
        "backup_capable": None,
        "battery_power": 3000,
        "load_power": 4000,
        "grid_status": "Inactive",
        "grid_services_active": None,
        "grid_power": 1000,
        "grid_services_power": None,
        "generator_power": 500,
        "island_status": "off_grid",
        "storm_mode_active": None,
        "timestamp": None,
        "wall_connectors": None,
    }
}

# entity_id -> state once the merge overlays the local snapshot. Power/energy
# keys convert W/Wh to kW/kWh; the two enums pass through.
_LOCAL_LIVE_STATES = {
    "sensor.energy_site_solar_power": "2.0",
    "sensor.energy_site_energy_left": "20.0",
    "sensor.energy_site_total_pack_energy": "40.0",
    "sensor.energy_site_percentage_charged": "80.0",
    "sensor.energy_site_battery_power": "3.0",
    "sensor.energy_site_load_power": "4.0",
    "sensor.energy_site_grid_power": "1.0",
    "sensor.energy_site_generator_power": "0.5",
    "sensor.energy_site_island_status": "off_grid",
    "binary_sensor.energy_site_grid_status": STATE_OFF,
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_paired_site_live_reads_merge_over_cloud(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
) -> None:
    """A paired site overlays the ten local live keys onto the cloud document."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_live_status.side_effect = lambda: deepcopy(_LOCAL_LIVE_STATUS)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch(
            "homeassistant.components.teslemetry.PLATFORMS",
            [Platform.SENSOR, Platform.BINARY_SENSOR],
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        live_coordinator = entry.runtime_data.energysites[0].live_coordinator
        # The local poll runs on its own timer, never through update_interval.
        assert live_coordinator.update_interval is None
        # Before the first LAN poll the merge base is the cloud cold read.
        assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"

        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # One shared gateway read feeds every locally-owned entity.
    assert mock_powerwall_live_status.await_count == 1
    for entity_id, expected in _LOCAL_LIVE_STATES.items():
        assert hass.states.get(entity_id).state == expected

    # Keys the gateway cannot serve keep their cloud values rather than the
    # local None, so the merge never blanks a working cloud reading.
    assert hass.states.get("sensor.energy_site_grid_services_power").state == "0.0"
    assert hass.states.get("binary_sensor.energy_site_backup_capable").state == STATE_ON
    assert (
        hass.states.get("binary_sensor.energy_site_grid_services_active").state
        == STATE_OFF
    )


async def test_paired_site_config_reads_merge_over_cloud(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_local_config: AsyncMock,
) -> None:
    """A paired site overlays the two local config keys onto the cloud site_info."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_local_config.return_value = {
        "backup_reserve_percent": 20.0,
        "default_real_mode": "autonomous",
    }

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch(
            "homeassistant.components.teslemetry.PLATFORMS",
            [Platform.NUMBER, Platform.SELECT],
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        info_coordinator = entry.runtime_data.energysites[0].info_coordinator
        # The local poll runs on its own timer, never through update_interval.
        assert info_coordinator.update_interval is None
        # Before the first LAN poll the config-backed entities read the cloud.
        assert (
            hass.states.get("select.energy_site_operation_mode").state
            == "self_consumption"
        )

        freezer.tick(ENERGY_CONFIG_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert mock_powerwall_local_config.await_count == 1
    assert hass.states.get("number.energy_site_backup_reserve").state == "20.0"
    assert hass.states.get("select.energy_site_operation_mode").state == "autonomous"
    # A cloud-only config key (not locally owned) keeps its cloud value.
    assert hass.states.get("select.energy_site_allow_export").state == "pv_only"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cloud_push_between_local_ticks_keeps_owned_key(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
    mock_energy_live_stream: MagicMock,
) -> None:
    """A cloud stream push must not revert a locally-owned key while local is healthy."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_live_status.side_effect = lambda: deepcopy(_LOCAL_LIVE_STATUS)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # A healthy local poll makes solar_power a locally-owned value.
        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.energy_site_solar_power").state == "2.0"

        # A cloud push arriving before the next local tick carries its own
        # solar_power (owned) and grid_services_power (cloud-only).
        push = deepcopy(LIVE_STATUS["response"])
        push["solar_power"] = 9999
        push["grid_services_power"] = 7000
        mock_energy_live_stream.send(push)
        await hass.async_block_till_done()

    # The owned key still reflects the last local poll, not the cloud push...
    assert hass.states.get("sensor.energy_site_solar_power").state == "2.0"
    # ...while a cloud-only key does take the pushed value, proving the push was
    # merged against the cached local snapshot rather than dropped or stored raw.
    assert hass.states.get("sensor.energy_site_grid_services_power").state == "7.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_paired_site_live_read_failure_falls_back_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
) -> None:
    """A failed local live poll shows cloud values (never unavailable) and recovers."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_live_status.side_effect = PowerwallError("gateway unreachable")

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        # The first poll fails: the owned key falls back to the cloud value
        # rather than going unavailable, and setup is unaffected.
        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"

        # The next poll succeeds and the owned key follows the local reading.
        mock_powerwall_live_status.side_effect = lambda: deepcopy(_LOCAL_LIVE_STATUS)
        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == "2.0"


async def test_paired_site_config_read_failure_falls_back_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_local_config: AsyncMock,
) -> None:
    """A failed local config poll shows cloud values (never unavailable) and recovers."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_local_config.side_effect = PowerwallError("gateway unreachable")

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SELECT]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        # The first poll fails: the owned key falls back to the cloud value
        # rather than going unavailable.
        freezer.tick(ENERGY_CONFIG_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get("select.energy_site_operation_mode").state
            == "self_consumption"
        )

        # The next poll succeeds and the owned key follows the local reading.
        mock_powerwall_local_config.side_effect = None
        mock_powerwall_local_config.return_value = {"default_real_mode": "autonomous"}
        freezer.tick(ENERGY_CONFIG_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("select.energy_site_operation_mode").state == "autonomous"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unpaired_site_reads_cloud_only(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
    mock_powerwall_local_config: AsyncMock,
) -> None:
    """An unpaired site never polls a gateway; its coordinators stay stream-only."""
    entry = await setup_platform(hass, [Platform.SENSOR, Platform.SELECT])

    energysite = entry.runtime_data.energysites[0]
    assert not isinstance(energysite.api, EnergySiteRouter)
    # No local polling is scheduled on either coordinator.
    assert energysite.live_coordinator.update_interval is None
    assert energysite.info_coordinator.update_interval is None

    # Advancing past both local intervals reads no gateway and changes nothing.
    freezer.tick(ENERGY_CONFIG_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_powerwall_live_status.await_count == 0
    assert mock_powerwall_local_config.await_count == 0
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"
    assert (
        hass.states.get("select.energy_site_operation_mode").state == "self_consumption"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_local_live_poll_survives_stream_push_storm(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
    mock_energy_live_stream: MagicMock,
) -> None:
    """The local live poll keeps its 5s cadence under a storm of stream pushes.

    A stream push must never reset the local poll timer. Against a poll driven by
    ``update_interval`` each push restarts the timer, so a push every second
    perpetually postpones the poll and it never fires; on its own timer the poll
    fires on every 5-second boundary regardless of the push rate.
    """
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_live_status.side_effect = lambda: deepcopy(_LOCAL_LIVE_STATUS)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_powerwall_live_status.await_count == 0

        # A stream push arrives every second for 20 seconds.
        for second in range(1, 21):
            push = deepcopy(LIVE_STATUS["response"])
            push["solar_power"] = 1000 * second
            mock_energy_live_stream.send(push)
            freezer.tick(timedelta(seconds=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

    # The 5-second poll fired on each of its four boundaries despite a push every
    # second, and the owned key reflects the local reading, not the last push.
    assert mock_powerwall_live_status.await_count == 4
    assert hass.states.get("sensor.energy_site_solar_power").state == "2.0"


async def test_local_config_poll_does_not_clear_stream_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_add_connection_listener: MagicMock,
    mock_powerwall_local_config: AsyncMock,
) -> None:
    """A local config poll never clears the info coordinator's stream error.

    Cloud-only site-info entities have no local source, so their availability is
    stream-owned. A successful local poll refreshes the locally-owned keys in the
    coordinator data without clearing the stream error or making the cloud-only
    entities available with stale values.
    """
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_local_config.return_value = {"default_real_mode": "autonomous"}

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SELECT]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        info_coordinator = entry.runtime_data.energysites[0].info_coordinator

        # The stream drops, failing the stream-owned info coordinator.
        mock_add_connection_listener.send(False)
        await hass.async_block_till_done()
        assert info_coordinator.last_update_success is False
        assert (
            hass.states.get("select.energy_site_operation_mode").state
            == STATE_UNAVAILABLE
        )
        assert (
            hass.states.get("select.energy_site_allow_export").state
            == STATE_UNAVAILABLE
        )

        # A successful local config poll fires while the stream is still down.
        freezer.tick(ENERGY_CONFIG_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert mock_powerwall_local_config.await_count == 1
    # The locally-owned key is refreshed in the coordinator data...
    assert info_coordinator.data["default_real_mode"] == "autonomous"
    # ...but the poll left the stream error untouched, so the cloud-only entity
    # stays unavailable rather than surfacing a stale cloud value.
    assert info_coordinator.last_update_success is False
    assert hass.states.get("select.energy_site_allow_export").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_local_poll_timer_cancelled_on_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powerwall_live_status: AsyncMock,
) -> None:
    """Unloading the entry cancels the local poll timer; no timer is leaked."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    mock_powerwall_live_status.side_effect = lambda: deepcopy(_LOCAL_LIVE_STATUS)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        freezer.tick(ENERGY_LIVE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_powerwall_live_status.await_count == 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    # Advancing past the interval after unload polls the gateway no further.
    freezer.tick(ENERGY_LIVE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_powerwall_live_status.await_count == 1
