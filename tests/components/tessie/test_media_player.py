"""Test the Tessie media player platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


async def test_media_player(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_get_state,
    mock_get_status,
) -> None:
    """Tests that the media player entity is correct when idle."""

    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-paused")

        # The refresh fixture has music playing
        freezer.tick(WAIT)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-playing"
        )
