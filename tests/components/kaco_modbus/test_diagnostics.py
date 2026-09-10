"""Test the KACO Modbus diagnostics."""

import json

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL

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


async def test_diagnostics_does_not_leak_the_serial_number(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the serial is redacted, and absent from the raw registers.

    Model 1 carries it in the clear, so a raw map that reached back over that
    block would hand it to anyone who decoded the dump.
    """
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["serial_number"] == "**REDACTED**"
    assert MOCK_SERIAL not in json.dumps(diag)
