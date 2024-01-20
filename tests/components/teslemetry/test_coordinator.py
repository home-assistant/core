"""Test the Tessie init."""
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import WAKE_UP_FAILURE


async def test_first_refresh(
    hass: HomeAssistant, mock_teslemetry, freezer: FrozenDateTimeFactory
) -> None:
    """Test first coordinator refresh."""

    mock_teslemetry.vehicle.specific.return_value.wake_up = AsyncMock(WAKE_UP_FAILURE)
    entry = await setup_platform(hass)
    # assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_teslemetry.vehicle.specific.return_value.wake_up.assert_called_once()
    mock_teslemetry.vehicle.specific.return_value.wake_up.reset_mock()
    await freezer.tick(5)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
