"""Tests for the KEBA charging station against each captured station state."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeKebaStation

# Sent by the station on its own while charging: no "ID", no trailing newline.
PUSH_DATAGRAM = b'{"E pres": 12965}'  # codespell:ignore pres


@pytest.mark.parametrize("corpus", ["p30_plugged.json", "p30_charging.json"])
async def test_states_per_station_state(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the entity states for a car plugged in, and for a car charging."""
    entity_ids = sorted(
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.platform == DOMAIN
    )
    assert len(entity_ids) == 10
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) == snapshot(name=entity_id)


async def test_push_datagram_currently_ignored(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test a datagram without "ID" changes nothing.

    The library drops any datagram without "ID", so the station's own
    progress messages only show up with the next poll.
    """
    setup_keba.broadcast(PUSH_DATAGRAM)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.keba_p30_session_energy").state == "43.59"
