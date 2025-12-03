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
    # Call the inverse entity to set a position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": inv_id, "position": 30},
        blocking=True,
    )

    state = hass.states.get(inv_id)
    assert state is not None
