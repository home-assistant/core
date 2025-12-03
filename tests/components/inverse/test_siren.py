"""Inverse siren platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_siren_toggle(hass: HomeAssistant) -> None:
    """Verify turn_on/turn_off are accepted on inverse siren entity."""
    hass.states.async_set("siren.sample", "off")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "siren.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "siren.abc"
    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": inv_id}, blocking=True
    )
    await hass.services.async_call(
        "siren", "turn_off", {"entity_id": inv_id}, blocking=True
    )

    assert hass.states.get(inv_id) is not None
