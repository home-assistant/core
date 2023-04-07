"""Test Brottsplatskartan component setup process."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.brottsplatskartan.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_CONFIG = {
    "latitude": None,
    "longitude": None,
    "area": "N/A",
    "app_id": "ha-1234567890",
}


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test load and unload entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        unique_id="bpk-home",
        title="BPK-HOME",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.brottsplatskartan.sensor.BrottsplatsKartan",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.bpk_home")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.bpk_home")
    assert not state
