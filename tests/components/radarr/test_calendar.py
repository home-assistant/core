"""The tests for Radarr calendar platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import setup_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    ("tested_time", "zone"),
    [
        (
            "2021-12-02 00:00:00-08:00",
            "US/Pacific",
        ),
        (
            "2021-12-03 09:00:00+01:00",
            "Europe/London",
        ),
    ],
    ids=("Pacific", "London"),
)
async def test_calendar(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    tested_time: str,
    zone: str,
) -> None:
    """Test for successfully setting up the Radarr platform."""
    tz = await dt_util.async_get_time_zone(zone)
    dt_util.set_default_time_zone(tz)
    freezer.move_to(tested_time)
    await setup_integration(hass, aioclient_mock)

    assert hass.states.get("calendar.mock_title") == snapshot

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.mock_title")
    assert state.state == STATE_OFF
    assert len(state.attributes) == 1
    assert state.attributes.get("release_type") is None
