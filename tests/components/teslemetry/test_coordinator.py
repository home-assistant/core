"""Test the Tessie init."""
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from tesla_fleet_api.exceptions import TeslaFleetError, VehicleOffline

from homeassistant.components.teslemetry.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import WAKE_UP_FAILURE, WAKE_UP_SUCCESS

from tests.common import async_fire_time_changed


async def test_first_refresh(
    hass: HomeAssistant, mock_teslemetry, freezer: FrozenDateTimeFactory
) -> None:
    """Test first coordinator refresh but vehicle is asleep."""

    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.return_value = (
        WAKE_UP_FAILURE
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.assert_called_once()

    mock_teslemetry.reset_mock()
    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.return_value = (
        WAKE_UP_SUCCESS
    )
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.assert_called_once()
    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.assert_called_once()
    assert entry.state is ConfigEntryState.LOADED


async def test_first_refresh_error(hass: HomeAssistant, mock_teslemetry) -> None:
    """Test first coordinator refresh with an error."""
    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.side_effect = (
        TeslaFleetError
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_refresh_offline(
    hass: HomeAssistant, mock_teslemetry, freezer: FrozenDateTimeFactory
) -> None:
    """Test coordinator refresh with an error."""
    entry = await setup_platform(hass, [Platform.CLIMATE])
    assert entry.state is ConfigEntryState.LOADED
    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.assert_called_once()
    mock_teslemetry.reset_mock()

    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.side_effect = VehicleOffline
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.assert_called_once()


async def test_refresh_error(hass: HomeAssistant, mock_teslemetry) -> None:
    """Test coordinator refresh with an error."""
    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
