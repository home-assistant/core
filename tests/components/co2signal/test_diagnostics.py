"""Test the CO2Signal diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("setup_integration")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot(exclude=props("created_at", "modified_at"))
