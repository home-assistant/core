"""Tests for the Samsung Infrared base entity."""

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID


@pytest.mark.usefixtures("init_integration")
async def test_entity_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test entity becomes unavailable when IR entity is unavailable."""
    entity_id = "media_player.samsung_tv"

    # Initially available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Make IR entity unavailable
    hass.states.async_set(MOCK_INFRARED_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Restore IR entity
    hass.states.async_set(MOCK_INFRARED_ENTITY_ID, "2026-01-01T00:00:00.000")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
