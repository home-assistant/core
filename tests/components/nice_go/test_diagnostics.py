"""Test diagnostics of Nice G.O.."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-08-27")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry, [])
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == snapshot(
        exclude=props("created_at", "modified_at", "refresh_token_creation_time")
    )
