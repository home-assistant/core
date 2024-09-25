"""Tests for the diagnostics data provided by the BSBLan integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics_data == snapshot
