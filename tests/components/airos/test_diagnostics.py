"""Diagnostic tests for airOS."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airos.coordinator import AirOS8Data
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_airos_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    ap_fixture: AirOS8Data,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
