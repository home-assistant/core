"""Tests for LANBON diagnostics."""

from homeassistant.core import HomeAssistant

from .conftest import TOKEN

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
) -> None:
    """Diagnostics must not include the token."""
    entry = setup_integration
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    dumped = str(diag)
    assert TOKEN not in dumped
    assert diag["entry"]["gateway_id"] == entry.unique_id
    assert diag["info"]["api_enabled"] is True
    switches = diag["switch_components"]
    assert any(row["component_id"] == "switch:1" for row in switches)
    assert all(row["type"] == "switch" for row in switches)
