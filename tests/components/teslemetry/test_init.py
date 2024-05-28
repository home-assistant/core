"""Test the Teslemetry init."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.components.teslemetry.coordinator import (
    VEHICLE_INTERVAL,
    VEHICLE_WAIT,
)
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed

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
    hass: HomeAssistant, mock_products, side_effect, state
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


# Vehicle Coordinator
async def test_vehicle_refresh_offline(
    hass: HomeAssistant, mock_vehicle_data, freezer: FrozenDateTimeFactory
) -> None:
    """Test coordinator refresh with an error."""
    entry = await setup_platform(hass, [Platform.CLIMATE])
    assert entry.state is ConfigEntryState.LOADED
    mock_vehicle_data.assert_called_once()
    mock_vehicle_data.reset_mock()

    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_vehicle_data.assert_called_once()


@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_vehicle_refresh_error(
    hass: HomeAssistant, mock_vehicle_data, side_effect, state
) -> None:
    """Test coordinator refresh with an error."""
    mock_vehicle_data.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


async def test_vehicle_sleep(
    hass: HomeAssistant, mock_vehicle_data, freezer: FrozenDateTimeFactory
) -> None:
    """Test coordinator refresh with an error."""
    await setup_platform(hass, [Platform.CLIMATE])
    assert mock_vehicle_data.call_count == 1

    freezer.tick(VEHICLE_WAIT + VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Let vehicle sleep, no updates for 15 minutes
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # No polling, call_count should not increase
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # No polling, call_count should not increase
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 2

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Vehicle didn't sleep, go back to normal
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 3

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Regular polling
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 4

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    # Vehicle active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 5

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Dont let sleep when active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 6

    freezer.tick(VEHICLE_WAIT)
    async_fire_time_changed(hass)
    # Dont let sleep when active
    await hass.async_block_till_done()
    assert mock_vehicle_data.call_count == 7


# Test Energy Live Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_live_refresh_error(
    hass: HomeAssistant, mock_live_status, side_effect, state
) -> None:
    """Test coordinator refresh with an error."""
    mock_live_status.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state


# Test Energy Site Coordinator
@pytest.mark.parametrize(("side_effect", "state"), ERRORS)
async def test_energy_site_refresh_error(
    hass: HomeAssistant, mock_site_info, side_effect, state
) -> None:
    """Test coordinator refresh with an error."""
    mock_site_info.side_effect = side_effect
    entry = await setup_platform(hass)
    assert entry.state is state
