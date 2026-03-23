"""Tests for the Huum diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_huum: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == snapshot


async def test_diagnostics_without_coordinator_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_huum: AsyncMock,
) -> None:
    """Test diagnostics when coordinator data is unavailable."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    mock_config_entry.runtime_data.data = None

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["last_exception"] is None
    assert "data" not in diagnostics
