"""Tests for the Appartme sensor platform."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN

from tests.common import MockConfigEntry


async def test_sensor_entities(hass, mock_appartme_api):
    """Test the Appartme sensor entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": {"access_token": "test-access-token"}},
    )
    config_entry.add_to_hass(hass)

    # Mock API responses
    device_id = "device123"
    mock_appartme_api.fetch_devices.return_value = [
        {"deviceId": device_id, "type": "mm", "name": "Main Module"}
    ]
    mock_appartme_api.fetch_device_details.return_value = {
        "deviceId": device_id,
        "type": "mm",
        "name": "Main Module",
        "properties": [
            {"propertyId": "phase_1_current", "mode": "read"},
            {"propertyId": "phase_2_current", "mode": "read"},
            {"propertyId": "phase_3_current", "mode": "read"},
            {"propertyId": "phase_1_voltage", "mode": "read"},
            {"propertyId": "phase_1_power", "mode": "read"},
            # Add other properties as needed
        ],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [
            {"propertyId": "phase_1_current", "value": 1.0, "mode": "read"},
            {"propertyId": "phase_2_current", "value": 2.0, "mode": "read"},
            {"propertyId": "phase_3_current", "value": 3.0, "mode": "read"},
            {"propertyId": "phase_1_voltage", "value": 230.0, "mode": "read"},
            {"propertyId": "phase_1_power", "value": 100.0, "mode": "read"},
            # Add other property values as needed
        ]
    }

    with patch(
        "homeassistant.components.appartme.AppartmeCloudAPI",
        return_value=mock_appartme_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test individual phase current sensors
    phase_1_current = hass.states.get("sensor.main_module_current_phase_1")
    phase_2_current = hass.states.get("sensor.main_module_current_phase_2")
    phase_3_current = hass.states.get("sensor.main_module_current_phase_3")

    assert phase_1_current.state == "1.0"
    assert phase_2_current.state == "2.0"
    assert phase_3_current.state == "3.0"

    # Test total current sensor
    total_current = hass.states.get("sensor.main_module_total_current")
    assert total_current.state == "6.0"

    # Test phase voltage sensor
    phase_1_voltage = hass.states.get("sensor.main_module_voltage_phase_1")
    assert phase_1_voltage.state == "230.0"

    # Test phase power sensor
    phase_1_power = hass.states.get("sensor.main_module_power_phase_1")
    assert phase_1_power.state == "100.0"
