"""The tests for Radarr calendar platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.radarr.const import CONF_UPCOMING_DAYS
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
async def test_calendar_respects_upcoming_days_option(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the calendar coordinator uses configured upcoming days."""
    entry = await setup_integration(
        hass,
        aioclient_mock,
        options={CONF_UPCOMING_DAYS: 1},
    )
    coordinator = entry.runtime_data.calendar

    with patch.object(
        coordinator, "async_get_events", AsyncMock(return_value=[])
    ) as mock_async_get_events:
        await coordinator.async_refresh()

    start_date, end_date = mock_async_get_events.await_args.args
    assert end_date - start_date == timedelta(days=1)
