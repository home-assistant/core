"""The sensor tests for the powerwall platform."""

from asynctest import patch

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import UNIT_PERCENTAGE
from homeassistant.setup import async_setup_component

from .mocks import _mock_get_config, _mock_powerwall_with_fixtures


async def test_sensors(hass):
    """Test creation of the sensors."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
        await hass.async_block_till_done()

    device_registry = await hass.helpers.device_registry.async_get_registry()
    reg_device = device_registry.async_get_device(
        identifiers={("powerwall", "TG0123456789AB_TG9876543210BA")}, connections=set(),
    )
    assert reg_device.model == "PowerWall 2 (GW1)"
    assert reg_device.sw_version == "1.45.1"
    assert reg_device.manufacturer == "Tesla"
    assert reg_device.name == "MySite"

    state = hass.states.get("sensor.powerwall_site_now")
    assert state.state == "0.032"
    expected_attributes = {
        "frequency": 60,
        "energy_exported": 10429451.9916853,
        "energy_imported": 4824191.60668611,
        "instant_average_voltage": 120.650001525879,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Site Now",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_load_now")
    assert state.state == "1.971"
    expected_attributes = {
        "frequency": 60,
        "energy_exported": 1056797.48917483,
        "energy_imported": 4692987.91889705,
        "instant_average_voltage": 120.650001525879,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Load Now",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_battery_now")
    assert state.state == "-8.55"
    expected_attributes = {
        "frequency": 60.014,
        "energy_exported": 3620010,
        "energy_imported": 4216170,
        "instant_average_voltage": 240.56,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Battery Now",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_solar_now")
    assert state.state == "10.49"
    expected_attributes = {
        "frequency": 60,
        "energy_exported": 9864205.82222448,
        "energy_imported": 28177.5358355867,
        "instant_average_voltage": 120.685001373291,
        "unit_of_measurement": "kW",
        "friendly_name": "Powerwall Solar Now",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value

    state = hass.states.get("sensor.powerwall_charge")
    assert state.state == "47"
    expected_attributes = {
        "unit_of_measurement": UNIT_PERCENTAGE,
        "friendly_name": "Powerwall Charge",
        "device_class": "battery",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value
