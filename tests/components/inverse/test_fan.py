"""Inverse fan platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_fan_toggle(hass: HomeAssistant) -> None:
    """Verify turn_on/turn_off are accepted on inverse fan entity."""
    hass.states.async_set("fan.sample", "on")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "fan.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "fan.abc"
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": inv_id}, blocking=True
    )
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": inv_id}, blocking=True
    )

    assert hass.states.get(inv_id) is not None
