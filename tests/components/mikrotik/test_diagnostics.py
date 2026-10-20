"""Tests for Mikrotik diagnostics platform."""

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_mikrotik_entry


@pytest.mark.freeze_time("2026-01-01T12:00:00+00:00")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Mikrotik config entry diagnostics."""
    config_entry = await setup_mikrotik_entry(hass)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
