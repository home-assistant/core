"""The sensor tests for the powerwall platform."""
from unittest.mock import patch

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, PERCENTAGE
from homeassistant.helpers import device_registry as dr

from .mocks import _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test creation of the sensors."""

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

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={("powerwall", "TG0123456789AB_TG9876543210BA")},
    )
    assert reg_device.model == "PowerWall 2 (GW1)"
    assert reg_device.sw_version == "1.45.1"
    assert reg_device.manufacturer == "Tesla"
    assert reg_device.name == "MySite"

    state = hass.states.get("sensor.powerwall_site_now")
    assert state.state == "0.032"
    expected_attributes = {
        "frequency": 60,
        "energy_exported_(in_kW)": 10429.5,
        "energy_imported_(in_kW)": 4824.2,
        "instant_average_voltage": 120.7,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Site Now",
        "device_class": "power",
        "is_active": False,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_load_now")
    assert state.state == "1.971"
    expected_attributes = {
        "frequency": 60,
        "energy_exported_(in_kW)": 1056.8,
        "energy_imported_(in_kW)": 4693.0,
        "instant_average_voltage": 120.7,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Load Now",
        "device_class": "power",
        "is_active": True,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_battery_now")
    assert state.state == "-8.55"
    expected_attributes = {
        "frequency": 60.0,
        "energy_exported_(in_kW)": 3620.0,
        "energy_imported_(in_kW)": 4216.2,
        "instant_average_voltage": 240.6,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Battery Now",
        "device_class": "power",
        "is_active": True,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_solar_now")
    assert state.state == "10.49"
    expected_attributes = {
        "frequency": 60,
        "energy_exported_(in_kW)": 9864.2,
        "energy_imported_(in_kW)": 28.2,
        "instant_average_voltage": 120.7,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Solar Now",
        "device_class": "power",
        "is_active": True,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_charge")
    assert state.state == "47"
    expected_attributes = {
        "unit_of_measurement": PERCENTAGE,
        "friendly_name": "Powerwall Charge",
        "device_class": "battery",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value
