"""Test the Sofar Inverter Modbus diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_redacts_serial_number(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the serial number is redacted, both as a field and as raw ASCII."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["serial_number"] == "**REDACTED**"
    holding = diag["raw"]["holding"]
    for address in range(0x0445, 0x044C):
        assert str(address) not in holding
