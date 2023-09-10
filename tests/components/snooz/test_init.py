"""Test Snooz configuration."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import (
    SNOOZ_SERVICE_INFO_NOT_PAIRING,
    SnoozFixture,
    create_mock_snooz,
    create_mock_snooz_config_entry,
)


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_removing_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Tests setup and removal of a config entry, ensuring connections are cleaned up."""
    await hass.config_entries.async_remove(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_reloading_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Test reloading an entry disconnects any existing connections."""
    await hass.config_entries.async_reload(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected


async def test_v1_migration(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests entry migration from v1 -> v2."""

    async def _async_process_advertisements(
        _hass, _callback, _matcher, _mode, _timeout
    ):
        # pairing mode is not required since we already stored the password
        assert _callback(SNOOZ_SERVICE_INFO_NOT_PAIRING)
        return SNOOZ_SERVICE_INFO_NOT_PAIRING

    with patch(
        "homeassistant.components.snooz.async_process_advertisements",
        _async_process_advertisements,
    ):
        device = await create_mock_snooz()
        entry = await create_mock_snooz_config_entry(hass, device, version=1)
        assert entry == snapshot
