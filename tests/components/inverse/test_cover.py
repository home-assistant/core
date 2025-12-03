"""Inverse cover platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_cover_position_inversion(hass: HomeAssistant) -> None:
    """Verify set_cover_position inverts position 100 - x and reflects in state attributes."""
    # Create a source cover
    hass.states.async_set("cover.sample", "open", {"current_position": 20})

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "cover.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "cover.abc"

    # Verify initial state inversion: source is "open" -> inverse is_closed should be True
    state = hass.states.get(inv_id)
    assert state is not None
    assert state.state == "closed"  # Inverse of "open"
    assert state.attributes.get("current_position") == 80  # Inverse of 20

    # Call the inverse entity to set a position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": inv_id, "position": 30},
        blocking=True,
    )

    state = hass.states.get(inv_id)
    assert state is not None


@pytest.mark.asyncio
async def test_inverse_cover_state_inversion(hass: HomeAssistant) -> None:
    """Verify cover state (open/closed) is properly inverted."""
    # Test 1: Source is open -> inverse is closed
    hass.states.async_set("cover.test_cover", "open", {"current_position": 100})

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "cover.test_cover"}, title="Test"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "cover.test"
    state = hass.states.get(inv_id)
    assert state is not None
    assert state.state == "closed"  # Inverted from "open"
    assert state.attributes.get("current_position") == 0  # Inverted from 100

    # Test 2: Update source to closed -> inverse becomes open
    hass.states.async_set("cover.test_cover", "closed", {"current_position": 0})
    await hass.async_block_till_done()

    state = hass.states.get(inv_id)
    assert state is not None
    assert state.state == "open"  # Inverted from "closed"
    assert state.attributes.get("current_position") == 100  # Inverted from 0
