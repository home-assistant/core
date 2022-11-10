"""Tests for data services used to interact with the combined energy API."""
from __future__ import annotations

from unittest.mock import AsyncMock

from combined_energy import CombinedEnergy
from combined_energy.exceptions import CombinedEnergyAuthError, CombinedEnergyError
import pytest

from homeassistant.components.combined_energy import coordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


class TestCombinedEnergyReadingsDataService:
    """Test CombinedEnergyReadingsDataService."""

    async def test_update_data__where_api_raises_an_auth_error(
        self, hass: HomeAssistant
    ):
        """If the API raises a Auth error raise ConfigEntryAuthFailed."""
        mock_api = AsyncMock(
            CombinedEnergy, readings=AsyncMock(side_effect=CombinedEnergyAuthError)
        )
        target = coordinator.CombinedEnergyReadingsDataService(hass, mock_api)

        with pytest.raises(ConfigEntryAuthFailed):
            await target.async_update_data()

    async def test_update_data__where_api_raises_an_error(self, hass: HomeAssistant):
        """If the API raises a generic error raise UpdateFailed."""
        mock_api = AsyncMock(
            CombinedEnergy, readings=AsyncMock(side_effect=CombinedEnergyError)
        )
        target = coordinator.CombinedEnergyReadingsDataService(hass, mock_api)

        with pytest.raises(UpdateFailed):
            await target.async_update_data()
