import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from frisquet_connect import async_setup_entry
from frisquet_connect.const import DOMAIN, PLATFORMS
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from utils import mock_endpoints, unstub_all


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry
):
    # Initialize the mocks
    mock_endpoints()

    # Test the feature
    with patch.object(
        mock_hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()
    ) as mock_forward:
        result = await async_setup_entry(mock_hass, mock_entry)

        # Assertions
        assert result is True
        assert mock_hass.data[DOMAIN][mock_entry.unique_id] is not None
        assert isinstance(
            mock_hass.data[DOMAIN][mock_entry.unique_id], FrisquetConnectCoordinator
        )
        mock_forward.assert_called_once_with(mock_entry, PLATFORMS)

    unstub_all()
