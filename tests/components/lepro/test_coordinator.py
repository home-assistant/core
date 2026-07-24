"""Tests for the Lepro coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.lepro.coordinator import LoproCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that UpdateFailed is raised when the API call fails."""
    client = MagicMock()
    client.async_get_devices = AsyncMock(side_effect=Exception("API error"))

    coordinator = LoproCoordinator(hass, client, mock_config_entry)

    with pytest.raises(UpdateFailed, match="Failed to fetch Lepro devices"):
        await coordinator._async_update_data()
