"""Fixtures for the Rainforest RAVEn tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from . import create_mock_device, create_mock_entry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device() -> Generator[AsyncMock]:
    """Mock a functioning RAVEn device."""
    mock_device = create_mock_device()
    with patch(
        "homeassistant.components.rainforest_raven.coordinator.RAVEnSerialDevice",
        return_value=mock_device,
    ):
        yield mock_device


@pytest.fixture
async def mock_entry(hass: HomeAssistant, mock_device: AsyncMock) -> MockConfigEntry:
    """Mock a functioning RAVEn config entry."""
    mock_entry = create_mock_entry()
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry
