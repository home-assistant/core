"""Test aidot."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.aidot.__init__ import (
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_async_setup_entry_calls_async_forward_entry_setups(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that async_setup_entry calls async_forward_entry_setups correctly."""
    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)
        hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_config_entry, ["light"]
        )


async def test_async_setup_entry_returns_true(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that async_setup_entry returns True."""

    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        result = await async_setup_entry(hass, mock_config_entry)
    assert result is True


async def test_async_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that async_unload_entry unloads the component correctly."""

    hass.data = MagicMock()
    with patch.object(
        hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
    ) as mock_unload:
        await async_unload_entry(hass, mock_config_entry)
        mock_unload.assert_called_once_with(mock_config_entry, ["light"])


async def test_async_unload_entry_fails(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that async_unload_entry handles failure correctly."""
    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)
        mock_unload.assert_called_once_with(mock_config_entry, ["light"])
        assert result is False
        assert hass.data.get(DOMAIN) is not None
