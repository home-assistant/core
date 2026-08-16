"""Test Sofar Inverter Modbus diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics, and that the serial number is redacted."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["serial_number"] == "**REDACTED**"
    assert result == snapshot
