"""Test the Tessie init."""


from freezegun.api import FrozenDateTimeFactory
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import async_fire_time_changed


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(hass: HomeAssistant, mock_products) -> None:
    """Test init with an authentication error."""

    mock_products.side_effect = InvalidToken
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_subscription_failure(hass: HomeAssistant, mock_products) -> None:
    """Test init with an client response error."""

    mock_products.side_effect = SubscriptionRequired
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_other_failure(hass: HomeAssistant, mock_products) -> None:
    """Test init with an client response error."""

    mock_products.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


# Vehicle Coordinator


async def test_vehicle_first_refresh_error(
    hass: HomeAssistant, mock_vehicle_data
) -> None:
    """Test first coordinator refresh with an error."""
    mock_vehicle_data.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


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


# Test Energy Live Coordinator
async def test_energy_live_refresh_error(hass: HomeAssistant, mock_live_status) -> None:
    """Test coordinator refresh with an error."""
    mock_live_status.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
