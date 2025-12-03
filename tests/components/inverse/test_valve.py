"""Inverse valve platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_valve_position_inversion(hass: HomeAssistant) -> None:
    """Verify set_valve_position is accepted and entity exists."""
    hass.states.async_set("valve.sample", "open", {"current_position": 10})

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "valve.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "valve.abc"
    await hass.services.async_call(
        "valve",
        "set_valve_position",
        {"entity_id": inv_id, "position": 70},
        blocking=True,
    )

    state = hass.states.get(inv_id)
    assert state is not None
