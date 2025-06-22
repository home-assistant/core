"""Test the Teslemetry init."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import PRODUCTS_MODERN, VEHICLE_DATA_ALT

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
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("binary_sensor.test_user_present")
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
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.test_user_present")
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
