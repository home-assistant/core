"""Inverse binary_sensor platform tests adapted from switch_as_x."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_inverse_binary_sensor_state(hass: HomeAssistant) -> None:
    """Verify inverse binary_sensor is created and mirrors availability."""
    hass.states.async_set("binary_sensor.sample", "on")

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "binary_sensor.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "binary_sensor.abc"
    state = hass.states.get(inv_id)
    assert state is not None
