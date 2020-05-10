"""The binary sensor tests for the powerwall platform."""

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component

from .mocks import _mock_get_config, _mock_powerwall_with_fixtures

from tests.async_mock import patch


async def test_sensors(hass):
    """Test creation of the binary sensors."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
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
        "region": "IEEE1547a:2014",
        "grid_code": "60Hz_240V_s_IEEE1547a_2014",
        "nominal_system_power_kW": 25,
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
