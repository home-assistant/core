"""The tests for Radarr calendar platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.radarr.const import DOMAIN
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import setup_integration

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
    hass.config.time_zone = zone
    freezer.move_to(tested_time)
    entry = await setup_integration(hass, aioclient_mock)
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["calendar"]

    assert hass.states.get("calendar.mock_title") == snapshot

    freezer.tick(timedelta(hours=16))
    await coordinator.async_refresh()

    state = hass.states.get("calendar.mock_title")
    assert state.state == STATE_OFF
    assert len(state.attributes) == 1
    assert state.attributes.get("release_type") is None
