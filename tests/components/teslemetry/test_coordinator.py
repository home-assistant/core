"""Test the Tessie init."""
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import WAKE_UP_FAILURE, WAKE_UP_SUCCESS

from tests.common import async_fire_time_changed


async def test_first_refresh(
    hass: HomeAssistant, mock_teslemetry, freezer: FrozenDateTimeFactory
) -> None:
    """Test first coordinator refresh."""

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
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_teslemetry.return_value.vehicle.specific.return_value.wake_up.assert_called_once()
    mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data.assert_called_once()
    assert entry.state is ConfigEntryState.LOADED
