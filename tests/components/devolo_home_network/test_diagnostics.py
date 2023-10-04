"""Tests for the devolo Home Network diagnostics."""
from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import configure_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_device")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == snapshot
