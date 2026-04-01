"""Tests for the LG Infrared integration."""

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MOCK_INFRARED_ENTITY_ID


async def check_availability_follows_ir_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Check that entity becomes unavailable when IR entity is unavailable."""
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
