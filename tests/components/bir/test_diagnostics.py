"""Tests for BIR diagnostics."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics output."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["entry_data"]["property_id"] == REDACTED
    assert result["entry_data"]["address"] == MOCK_ADDRESS
    assert "mixed_waste" in result["coordinator_data"]
    assert result["coordinator_data"]["mixed_waste"]["date"] == "2026-04-15"
