"""Tests for the diagnostics data provided by the Overkiz integration."""
import os
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    diagnostic_data = load_json_object_fixture("overkiz/setup_tahoma_switch.json")

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        get_diagnostic_data=AsyncMock(return_value=diagnostic_data),
        get_execution_history=AsyncMock(return_value=[]),
    ):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
            == snapshot
        )
