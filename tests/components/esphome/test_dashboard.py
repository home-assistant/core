"""Test ESPHome dashboard features."""
from unittest.mock import patch

from homeassistant.components.esphome import dashboard
from homeassistant.config_entries import ConfigEntryState


async def test_new_info_reload_config_entries(hass, init_integration, mock_dashboard):
    """Test config entries are reloaded when new info is set."""
    assert init_integration.state == ConfigEntryState.LOADED

    with patch("homeassistant.components.esphome.async_setup_entry") as mock_setup:
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == init_integration

    # Test it's a no-op when the same info is set
    with patch("homeassistant.components.esphome.async_setup_entry") as mock_setup:
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)

    assert len(mock_setup.mock_calls) == 0
