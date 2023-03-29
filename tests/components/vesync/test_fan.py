"""Tests for the fan module."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import get_entities, get_states


async def test_async_setup_entry__loaded_fans(
    hass: HomeAssistant,
    setup_platform,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    states = {}
    identifier = "air-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 3
    states[identifier] = get_states(hass, entities)

    identifier = "asd_sdfKIHG7IJHGwJGJ7GJ_ag5h3G55"
    entities = get_entities(hass, identifier)
    assert len(entities) == 2
    states[identifier] = get_states(hass, entities)

    identifier = "400s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 4
    states[identifier] = get_states(hass, entities)

    identifier = "600s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 4
    states[identifier] = get_states(hass, entities)

    assert states == snapshot
