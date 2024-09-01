"""Tests for the diagnostics data provided by the BSBLan integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("static_file", ["static.json"])
async def test_diagnostics(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    static_file: str,
) -> None:
    """Test diagnostics."""
    await mock_bsblan.set_static_values(static_file)

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics_data == snapshot
