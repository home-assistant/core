"""The tests for Radarr calendar platform."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.radarr.const import DEFAULT_UPCOMING_DAYS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_calendar(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for successfully setting up the Radarr platform."""
    freezer.move_to("2021-12-02 00:00:00-08:00")
    await setup_integration(hass, aioclient_mock)

    state = hass.states.get("calendar.mock_title")
    assert state.state == STATE_ON
    assert state.attributes.get("all_day") is True
    assert state.attributes.get("description") == "test2"
    assert state.attributes.get("end_time") == "2021-12-03 00:00:00"
    assert state.attributes.get("message") == "test"
    assert state.attributes.get("release_type") == "physicalRelease"
    assert state.attributes.get("start_time") == "2021-12-02 00:00:00"

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.mock_title")
    assert state.state == STATE_OFF
    assert len(state.attributes) == 1
    assert state.attributes.get("release_type") is None


@pytest.mark.freeze_time("2021-12-02 00:00:00-08:00")
async def test_calendar_uses_single_ranged_request(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the calendar coordinator fetches the fixed lookahead in one request."""
    entry = await setup_integration(hass, aioclient_mock)
    coordinator = entry.runtime_data.calendar

    with patch.object(
        coordinator.api_client, "async_get_calendar", AsyncMock(return_value=[])
    ) as mock_async_get_calendar:
        await coordinator.async_refresh()

    mock_async_get_calendar.assert_awaited_once_with(
        start_date=date(2021, 12, 2),
        end_date=date(2021, 12, 2) + timedelta(days=DEFAULT_UPCOMING_DAYS),
    )
