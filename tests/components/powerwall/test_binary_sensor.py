"""The binary sensor tests for the powerwall platform."""

from unittest.mock import patch

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, STATE_ON

from .mocks import _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test creation of the binary sensors."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.grid_status")
    assert state.state == STATE_ON
    expected_attributes = {"friendly_name": "Grid Status", "device_class": "power"}
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.powerwall_status")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "Powerwall Status",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.powerwall_connected_to_tesla")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "Powerwall Connected to Tesla",
        "device_class": "connectivity",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.powerwall_charging")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "Powerwall Charging",
        "device_class": "battery_charging",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())
