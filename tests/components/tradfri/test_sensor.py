"""Tradfri sensor platform tests."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

from homeassistant.components import tradfri
from homeassistant.helpers import entity_registry as er

from . import GATEWAY_ID
from .common import setup_integration
from .test_fan import mock_fan

from tests.common import MockConfigEntry


def mock_sensor(test_state: list, device_number=0):
    """Mock a tradfri sensor."""
    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"

    _mock_sensor = Mock(
        id=f"mock-sensor-id-{device_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=False,
        has_socket_control=False,
        has_blind_control=False,
        has_signal_repeater_control=False,
        has_air_purifier_control=False,
    )

    # Set state value, eg battery_level = 50, or has_air_purifier_control=True
    for state in test_state:
        setattr(dev_info_mock, state["attribute"], state["value"])

    _mock_sensor.name = f"tradfri_sensor_{device_number}"

    return _mock_sensor


async def test_battery_sensor(hass, mock_gateway, mock_api_factory):
    """Test that a battery sensor is correctly added."""
    mock_gateway.mock_devices.append(
        mock_sensor(test_state=[{"attribute": "battery_level", "value": 60}])
    )
    await setup_integration(hass)

    sensor_1 = hass.states.get("sensor.tradfri_sensor_0")
    assert sensor_1 is not None
    assert sensor_1.state == "60"
    assert sensor_1.attributes["unit_of_measurement"] == "%"
    assert sensor_1.attributes["device_class"] == "battery"


async def test_cover_battery_sensor(hass, mock_gateway, mock_api_factory):
    """Test that a battery sensor is correctly added for a cover (blind)."""
    mock_gateway.mock_devices.append(
        mock_sensor(
            test_state=[
                {"attribute": "battery_level", "value": 42, "has_blind_control": True}
            ]
        )
    )
    await setup_integration(hass)

    sensor_1 = hass.states.get("sensor.tradfri_sensor_0")
    assert sensor_1 is not None
    assert sensor_1.state == "42"
    assert sensor_1.attributes["unit_of_measurement"] == "%"
    assert sensor_1.attributes["device_class"] == "battery"


async def test_air_quality_sensor(hass, mock_gateway, mock_api_factory):
    """Test that a battery sensor is correctly added."""
    mock_gateway.mock_devices.append(
        mock_fan(
            test_state={
                "fan_speed": 10,
                "air_quality": 42,
                "filter_lifetime_remaining": 120,
            }
        )
    )
    await setup_integration(hass)

    sensor_1 = hass.states.get("sensor.tradfri_fan_0_air_quality")
    assert sensor_1 is not None
    assert sensor_1.state == "42"
    assert sensor_1.attributes["unit_of_measurement"] == "µg/m³"
    assert sensor_1.attributes["device_class"] == "aqi"


async def test_filter_time_left_sensor(hass, mock_gateway, mock_api_factory):
    """Test that a battery sensor is correctly added."""
    mock_gateway.mock_devices.append(
        mock_fan(
            test_state={
                "fan_speed": 10,
                "air_quality": 42,
                "filter_lifetime_remaining": 120,
            }
        )
    )
    await setup_integration(hass)

    sensor_1 = hass.states.get("sensor.tradfri_fan_0_filter_time_left")
    assert sensor_1 is not None
    assert sensor_1.state == "2"
    assert sensor_1.attributes["unit_of_measurement"] == "h"


async def test_sensor_observed(hass, mock_gateway, mock_api_factory):
    """Test that sensors are correctly observed."""
    sensor = mock_sensor(test_state=[{"attribute": "battery_level", "value": 60}])
    mock_gateway.mock_devices.append(sensor)
    await setup_integration(hass)
    assert len(sensor.observe.mock_calls) > 0


async def test_sensor_available(hass, mock_gateway, mock_api_factory):
    """Test sensor available property."""
    sensor = mock_sensor(
        test_state=[{"attribute": "battery_level", "value": 60}], device_number=1
    )
    sensor.reachable = True

    sensor2 = mock_sensor(
        test_state=[{"attribute": "battery_level", "value": 60}], device_number=2
    )
    sensor2.reachable = False

    mock_gateway.mock_devices.append(sensor)
    mock_gateway.mock_devices.append(sensor2)
    await setup_integration(hass)

    assert hass.states.get("sensor.tradfri_sensor_1").state == "60"
    assert hass.states.get("sensor.tradfri_sensor_2").state == "unavailable"


async def test_unique_id_migration(hass, mock_gateway, mock_api_factory):
    """Test unique ID is migrated from old format to new."""
    ent_reg = er.async_get(hass)
    old_unique_id = f"{GATEWAY_ID}-mock-sensor-id-0"
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "gateway_id": GATEWAY_ID,
        },
    )
    entry.add_to_hass(hass)

    # Version 1
    sensor_name = "sensor.tradfri_sensor_0"
    entity_name = sensor_name.split(".")[1]

    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        tradfri.DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )

    assert entity_entry.entity_id == sensor_name
    assert entity_entry.unique_id == old_unique_id

    # Add a sensor to the gateway so that it populates coordinator list
    sensor = mock_sensor(
        test_state=[{"attribute": "battery_level", "value": 60}],
    )
    mock_gateway.mock_devices.append(sensor)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(sensor_name)
    new_unique_id = f"{GATEWAY_ID}-mock-sensor-id-0-battery_level"
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("sensor", tradfri.DOMAIN, old_unique_id) is None
