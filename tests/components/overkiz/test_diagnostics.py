"""Tests for the diagnostics data provided by the Overkiz integration."""
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

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
    """Test diagnostics."""
    diagnostics = {"test": "test"}

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        get_diagnostic_data=AsyncMock(return_value=diagnostics),
        get_execution_history=AsyncMock(return_value=[]),
    ):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
            == snapshot
        )
