"""Tests for the diagnostics data provided by the System Monitor integration."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-02-24 15:00:00", tz_offset=0)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_added_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    ) == snapshot(exclude=props("last_update", "entry_id", "created_at", "modified_at"))


@pytest.mark.freeze_time("2024-02-24 15:00:00", tz_offset=0)
async def test_diagnostics_missing_items(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_psutil.net_if_addrs.return_value = None
    mock_psutil.net_io_counters.return_value = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(
        exclude=props("last_update", "entry_id", "created_at", "modified_at"),
        name="test_diagnostics_missing_items",
    )
