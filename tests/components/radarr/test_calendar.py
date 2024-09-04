"""The tests for Radarr calendar platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

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
