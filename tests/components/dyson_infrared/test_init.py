"""Tests for the Dyson Infrared config entry setup/unload."""

from unittest.mock import patch

from homeassistant.components.dyson_infrared import PLATFORMS, async_unload_entry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the Dyson Infrared config entry."""
    entry = MockConfigEntry(domain="dyson_infrared")
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await hass.config_entries.async_setup(entry.entry_id)

        assert result is True
        mock_forward.assert_called_once_with(entry, PLATFORMS)


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry forwards unload to platforms."""
    entry = MockConfigEntry(domain="dyson_infrared")
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ) as mock_unload:
        result = await async_unload_entry(hass, entry)

        assert result is True
        mock_unload.assert_called_once_with(entry, PLATFORMS)
