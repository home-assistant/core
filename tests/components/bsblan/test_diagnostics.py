"""Tests for the diagnostics data provided by the BSBLan integration."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("mock_bsblan", ["static.json", "static_F.json"], indirect=True)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics_data == snapshot
