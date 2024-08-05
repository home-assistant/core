"""Tests for myuplink sensor module."""

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

    state = hass.states.get("sensor.gotham_city_average_outdoor_temp_bt1")
    assert state is not None
    assert state.state == "-12.2"
    assert state.attributes == {
        "friendly_name": "Gotham City Average outdoor temp (BT1)",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
    }
