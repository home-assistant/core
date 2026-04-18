"""Tests for the Fumis coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from fumis import (
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisStoveOfflineError,
)
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    "side_effect",
    [
        FumisAuthenticationError,
        FumisStoveOfflineError,
        FumisConnectionError,
        FumisError,
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
) -> None:
    """Test coordinator handles errors and marks entities unavailable."""
    mock_fumis.update_info.side_effect = side_effect

    freezer.tick(timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.clou_duo")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_update_recovery(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator recovers after error."""
    mock_fumis.update_info.side_effect = FumisConnectionError

    freezer.tick(timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("climate.clou_duo"))
    assert state.state == STATE_UNAVAILABLE

    mock_fumis.update_info.side_effect = None

    freezer.tick(timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("climate.clou_duo"))
    assert state.state != STATE_UNAVAILABLE
