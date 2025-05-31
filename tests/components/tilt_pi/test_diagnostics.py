"""Test the Tilt Pi diagnostics."""

from unittest.mock import Mock

from homeassistant.components.tilt_pi.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test diagnostics."""
    mock_entry = Mock()
    mock_entry.data = {"host": "192.168.1.100", "port": 8080}
    mock_entry.runtime_data.data = {
        "temperature": 68,
        "gravity": 1.050,
        "color": "PURPLE",
    }

    result = await async_get_config_entry_diagnostics(hass, mock_entry)

    assert result == {
        "entry_data": {"host": "192.168.1.100", "port": 8080},
        "data": {"temperature": 68, "gravity": 1.050, "color": "PURPLE"},
    }
