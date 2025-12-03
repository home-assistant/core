"""Inverse switch platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_switch_toggle(hass: HomeAssistant) -> None:
    """Verify turn_on/turn_off are accepted on inverse switch entity."""
    hass.states.async_set("switch.sample", "off")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "switch.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "switch.abc"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": inv_id}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": inv_id}, blocking=True
    )

    assert hass.states.get(inv_id) is not None
