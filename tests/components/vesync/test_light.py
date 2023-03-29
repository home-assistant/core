"""Tests for the light module."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import get_entities, get_states


async def test_async_setup_entry__loaded_lights(
    hass: HomeAssistant,
    setup_platform,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    states = {}
    identifier = "dimmable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    identifier = "tunable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    identifier = "dimmable-switch"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    assert states == snapshot
