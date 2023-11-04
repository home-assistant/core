"""Define tests for the OurGroceries coordinator."""
from asyncio import TimeoutError as AsyncIOTimeoutError
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.ourgroceries.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("exception"),
    [
        (ClientError),
        (AsyncIOTimeoutError),
    ],
)
async def test_coordinator_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: None,
    ourgroceries: AsyncMock,
    exception: Exception,
) -> None:
    """Test error on coordinator update."""
    state = hass.states.get("todo.test_list")
    assert state.state == "0"

    ourgroceries.get_list_items.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("todo.test_list")
    assert state.state == STATE_UNAVAILABLE
