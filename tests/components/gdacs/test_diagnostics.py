"""Test GDACS diagnostics."""

from __future__ import annotations

from syrupy import SnapshotAssertion

from homeassistant.const import CONF_RADIUS, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CONFIG = {CONF_RADIUS: 200}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data=config_entry.data | CONFIG
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Artificially trigger update and collect events.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot
