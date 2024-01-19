"""Test the Tessie media player platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


async def test_media_player(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, snapshot: SnapshotAssertion
) -> None:
    """Tests that the media player entity is correct when idle."""

    assert len(hass.states.async_all("media_player")) == 0

    await setup_platform(hass)

    assert hass.states.async_all("media_player") == snapshot(name="idle")

    # Trigger coordinator refresh since it has a different fixture.
    freezer.tick(WAIT)
    async_fire_time_changed(hass)

    assert hass.states.async_all("media_player") == snapshot(name="playing")
