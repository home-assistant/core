"""Tests for myuplink switch module."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.f730_cu_3x400v_temporary_lux")
    assert state is not None
    assert state.state == "off"
    assert state.attributes == {
        "friendly_name": "F730 CU 3x400V Tempo­rary lux",
    }
