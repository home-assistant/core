"""Inverse lock platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_lock_services(hass: HomeAssistant) -> None:
    """Verify lock/unlock services are accepted on inverse lock entity."""
    hass.states.async_set("lock.sample", "locked")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "lock.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "lock.abc"
    await hass.services.async_call("lock", "lock", {"entity_id": inv_id}, blocking=True)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": inv_id}, blocking=True
    )

    state = hass.states.get(inv_id)
    assert state is not None
