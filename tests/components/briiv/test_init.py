"""Test Briiv integration setup."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.briiv import async_setup_entry, async_unload_entry
from homeassistant.components.briiv.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test",
        data={"host": "192.168.1.100", "port": 3334, "serial_number": "TEST123"},
        source="test",
        options={},
        unique_id="TEST123",
    )


async def test_setup_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setup of a config entry."""
    with patch(
        "custom_components.briiv.BriivAPI.start_listening", return_value=None
    ) as mock_start:
        assert await async_setup_entry(hass, mock_config_entry)
        mock_start.assert_called_once()

    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_fails(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setup fails if listening fails."""
    with (
        patch("custom_components.briiv.BriivAPI.start_listening", side_effect=OSError),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)


async def test_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading of a config entry."""
    # First set up the entry
    mock_api = AsyncMock()

    with patch("custom_components.briiv.BriivAPI", return_value=mock_api):
        assert await async_setup_entry(hass, mock_config_entry)

    # Then unload it
    assert await async_unload_entry(hass, mock_config_entry)
    mock_api.stop_listening.assert_called_once()
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
