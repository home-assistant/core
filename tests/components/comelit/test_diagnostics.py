"""Tests for Comelit Simplehome diagnostics platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics_bridge(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Bridge config entry diagnostics."""
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_serial_bridge_config_entry
    ) == snapshot(
        exclude=props(
            "entry_id",
            "created_at",
            "modified_at",
        )
    )


async def test_entry_diagnostics_vedo(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Vedo System config entry diagnostics."""
    await setup_integration(hass, mock_vedo_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_vedo_config_entry
    ) == snapshot(
        exclude=props(
            "entry_id",
            "created_at",
            "modified_at",
        )
    )
