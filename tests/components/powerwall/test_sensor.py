"""The sensor tests for the powerwall platform."""
from unittest.mock import Mock, patch

from tesla_powerwall.error import MissingAttributeError

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_IP_ADDRESS,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .mocks import _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant, entity_registry_enabled_by_default) -> None:
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

    state = hass.states.get("sensor.powerwall_load_now")
    assert state.state == "1.971"
    attributes = state.attributes
    assert attributes[ATTR_DEVICE_CLASS] == "power"
    assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "kW"
    assert attributes[ATTR_STATE_CLASS] == "measurement"
    assert attributes[ATTR_FRIENDLY_NAME] == "Powerwall Load Now"

    state = hass.states.get("sensor.powerwall_load_frequency_now")
    assert state.state == "60"
    attributes = state.attributes
    assert attributes[ATTR_DEVICE_CLASS] == "frequency"
    assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "Hz"
    assert attributes[ATTR_STATE_CLASS] == "measurement"
    assert attributes[ATTR_FRIENDLY_NAME] == "Powerwall Load Frequency Now"

    state = hass.states.get("sensor.powerwall_load_average_voltage_now")
    assert state.state == "120.7"
    attributes = state.attributes
    assert attributes[ATTR_DEVICE_CLASS] == "voltage"
    assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert attributes[ATTR_STATE_CLASS] == "measurement"
    assert attributes[ATTR_FRIENDLY_NAME] == "Powerwall Load Average Voltage Now"

    state = hass.states.get("sensor.powerwall_load_average_current_now")
    assert state.state == "0"
    attributes = state.attributes
    assert attributes[ATTR_DEVICE_CLASS] == "current"
    assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "A"
    assert attributes[ATTR_STATE_CLASS] == "measurement"
    assert attributes[ATTR_FRIENDLY_NAME] == "Powerwall Load Average Current Now"

    assert float(hass.states.get("sensor.powerwall_load_export").state) == 1056.8
    assert float(hass.states.get("sensor.powerwall_load_import").state) == 4693.0

    state = hass.states.get("sensor.powerwall_battery_now")
    assert state.state == "-8.55"

    assert float(hass.states.get("sensor.powerwall_battery_export").state) == 3620.0
    assert float(hass.states.get("sensor.powerwall_battery_import").state) == 4216.2

    state = hass.states.get("sensor.powerwall_solar_now")
    assert state.state == "10.49"

    assert float(hass.states.get("sensor.powerwall_solar_export").state) == 9864.2
    assert float(hass.states.get("sensor.powerwall_solar_import").state) == 28.2

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

    state = hass.states.get("sensor.powerwall_backup_reserve")
    assert state.state == "15"
    expected_attributes = {
        "unit_of_measurement": PERCENTAGE,
        "friendly_name": "Powerwall Backup Reserve",
        "device_class": "battery",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value


async def test_sensor_backup_reserve_unavailable(hass: HomeAssistant) -> None:
    """Confirm that backup reserve sensor is not added if data is unavailable from the device."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_backup_reserve_percentage = Mock(
        side_effect=MissingAttributeError(Mock(), "backup_reserve_percent", "operation")
    )

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

    state = hass.states.get("sensor.powerwall_backup_reserve")
    assert state is None
