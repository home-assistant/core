"""Test the Teslemetry init."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)

from homeassistant.components.teslemetry.const import CLIENT_ID, DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import CONFIG_V1, PRODUCTS_MODERN, UNIQUE_ID, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry

ERRORS = [
    (InvalidToken, ConfigEntryState.SETUP_ERROR),
    (SubscriptionRequired, ConfigEntryState.SETUP_ERROR),
    (TeslaFleetError, ConfigEntryState.SETUP_RETRY),
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


@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
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
        updated_device = device_registry.async_get_device(
            identifiers={(DOMAIN, "stale-vin")}
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

        mock_migrate.assert_called_once_with(
            CLIENT_ID, CONFIG_V1[CONF_ACCESS_TOKEN], hass.config.location_name
        )

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

        mock_migrate.assert_called_once_with(
            CLIENT_ID, CONFIG_V1[CONF_ACCESS_TOKEN], hass.config.location_name
        )

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
