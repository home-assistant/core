"""Tests for Homevolt diagnostics."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics == snapshot
