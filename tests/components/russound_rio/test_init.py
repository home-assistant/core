"""Test setting up and unloading Russound RIO."""

from unittest.mock import patch

import pytest

from homeassistant.components.russound_rio import async_setup_entry, async_unload_entry
from homeassistant.components.russound_rio.const import RUSSOUND_RIO_EXCEPTIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry, mock_russound
) -> None:
    """Test setting up the Russound RIO entry."""
    with (
        patch(
            "homeassistant.components.russound_rio.Russound", return_value=mock_russound
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as mock_forward_entry_setups,
    ):
        assert await async_setup_entry(hass, mock_config_entry)
        mock_russound.connect.assert_called_once()
        mock_forward_entry_setups.assert_called_once_with(
            mock_config_entry, [Platform.MEDIA_PLAYER]
        )
        assert mock_config_entry.runtime_data == mock_russound


@pytest.mark.asyncio
async def test_async_setup_entry_failure(
    hass: HomeAssistant, mock_config_entry, mock_russound
) -> None:
    """Test handling setup failure."""
    mock_russound.return_value.connect.side_effect = RUSSOUND_RIO_EXCEPTIONS[0](
        "Test Error"
    )

    with (
        pytest.raises(ConfigEntryError),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_russound
) -> None:
    """Test unloading the Russound RIO entry."""
    mock_config_entry.runtime_data = mock_russound

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ) as mock_unload_platforms:
        assert await async_unload_entry(hass, mock_config_entry)
        mock_unload_platforms.assert_called_once_with(
            mock_config_entry, [Platform.MEDIA_PLAYER]
        )
        mock_russound.close.assert_called_once()
