"""Test the Tessie media player platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.core import HomeAssistant

from .common import (
    TEST_STATE_OF_ALL_VEHICLES,
    TEST_VEHICLE_STATE_ONLINE,
    setup_platform,
)

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)

MEDIA_INFO_1 = TEST_STATE_OF_ALL_VEHICLES["results"][0]["last_state"]["vehicle_state"][
    "media_info"
]
MEDIA_INFO_2 = TEST_VEHICLE_STATE_ONLINE["vehicle_state"]["media_info"]


async def test_media_player_idle(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, snapshot: SnapshotAssertion
) -> None:
    """Tests that the media player entity is correct when idle."""

    assert len(hass.states.async_all("media_player")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("media_player")) == 1

    state = hass.states.get("media_player.test_media_player")
    assert state == snapshot

    # Trigger coordinator refresh since it has a different fixture.
    freezer.tick(WAIT)
    async_fire_time_changed(hass)

    state = hass.states.get("media_player.test_media_player")
    assert state == snapshot
