"""Test the SensorPush Cloud coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sensorpush_ha import SensorPushCloudError

from homeassistant.core import HomeAssistant

from .const import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.mark.data(MOCK_DATA)
async def test_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helper: AsyncMock,
) -> None:
    """Test we can update data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.data) == len(MOCK_DATA)


async def test_update_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helper: AsyncMock,
) -> None:
    """Test we can handle errors when updating data."""
    mock_helper.async_get_data.side_effect = SensorPushCloudError("test-message")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is None
