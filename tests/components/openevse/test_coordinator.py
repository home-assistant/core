"""Tests for the OpenEVSE coordinator."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.openevse.coordinator import OpenEVSEDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test coordinator raises UpdateFailed on timeout during update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: OpenEVSEDataUpdateCoordinator = mock_config_entry.runtime_data

    # Simulate timeout during update
    mock_charger.update.side_effect = TimeoutError("Connection timed out")

    with pytest.raises(UpdateFailed, match="Timeout communicating with charger"):
        await coordinator._async_update_data()
