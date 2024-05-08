"""Test the Tessie init."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from tesla_fleet_api.exceptions import (
    InvalidToken,
    PaymentRequired,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.components.teslemetry.coordinator import SYNC_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import WAKE_UP_ASLEEP, WAKE_UP_ONLINE

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

    mock_products.side_effect = PaymentRequired
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_other_failure(hass: HomeAssistant, mock_products) -> None:
    """Test init with an client response error."""

    mock_products.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


# Coordinator


async def test_first_refresh(
    hass: HomeAssistant,
    mock_wake_up,
    mock_vehicle_data,
    mock_products,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test first coordinator refresh but vehicle is asleep."""

    # Mock vehicle is asleep
    mock_wake_up.return_value = WAKE_UP_ASLEEP
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_wake_up.assert_called_once()

    # Reset mock and set vehicle to online
    mock_wake_up.reset_mock()
    mock_wake_up.return_value = WAKE_UP_ONLINE

    # Wait for the retry
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify we have loaded
    assert entry.state is ConfigEntryState.LOADED
    mock_wake_up.assert_called_once()
    mock_vehicle_data.assert_called_once()


async def test_first_refresh_error(hass: HomeAssistant, mock_wake_up) -> None:
    """Test first coordinator refresh with an error."""
    mock_wake_up.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_refresh_offline(
    hass: HomeAssistant, mock_vehicle_data, freezer: FrozenDateTimeFactory
) -> None:
    """Test coordinator refresh with an error."""
    entry = await setup_platform(hass, [Platform.CLIMATE])
    assert entry.state is ConfigEntryState.LOADED
    mock_vehicle_data.assert_called_once()
    mock_vehicle_data.reset_mock()

    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(timedelta(seconds=SYNC_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_vehicle_data.assert_called_once()


async def test_refresh_error(hass: HomeAssistant, mock_vehicle_data) -> None:
    """Test coordinator refresh with an error."""
    mock_vehicle_data.side_effect = TeslaFleetError
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
