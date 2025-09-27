"""Philips Hue binary_sensor platform tests for V2 bridge/api."""

from unittest.mock import Mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY


async def test_binary_sensors(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test if all v2 binary_sensors get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 7 binary_sensors should be created from test data

    # test motion sensor
    sensor = hass.states.get("binary_sensor.hue_motion_sensor_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Hue motion sensor Motion"
    assert sensor.attributes["device_class"] == "motion"

    # test entertainment room active sensor
    sensor = hass.states.get("binary_sensor.entertainmentroom_1")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Entertainmentroom 1"
    assert sensor.attributes["device_class"] == "running"

    # test contact sensor
    sensor = hass.states.get("binary_sensor.test_contact_sensor_opening")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Test contact sensor Opening"
    assert sensor.attributes["device_class"] == "opening"
    # test contact sensor disabled == state unknown
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "enabled": False,
            "id": "18802b4a-b2f6-45dc-8813-99cde47f3a4a",
            "type": "contact",
        },
    )
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.test_contact_sensor_opening")
    assert sensor.state == "unknown"

    # test tamper sensor
    sensor = hass.states.get("binary_sensor.test_contact_sensor_tamper")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Test contact sensor Tamper"
    assert sensor.attributes["device_class"] == "tamper"
    # test tamper sensor when no tamper reports exist
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": "d7fcfab0-69e1-4afb-99df-6ed505211db4",
            "tamper_reports": [],
            "type": "tamper",
        },
    )
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.test_contact_sensor_tamper")
    assert sensor.state == "off"

    # test camera_motion sensor
    sensor = hass.states.get("binary_sensor.test_camera_motion")
    assert sensor is not None
    assert sensor.state == "on"
    assert sensor.name == "Test Camera Motion"
    assert sensor.attributes["device_class"] == "motion"

    # test grouped motion sensor
    sensor = hass.states.get("binary_sensor.sensor_group_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Sensor group Motion"
    assert sensor.attributes["device_class"] == "motion"

    # test motion aware sensor
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Motion Aware Sensor 1"
    assert sensor.attributes["device_class"] == "motion"

    # test convenience area motion sensor
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1_convenience_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Motion Aware Sensor 1 Convenience Motion"
    assert sensor.attributes["device_class"] == "motion"


async def test_binary_sensor_add_update(
    hass: HomeAssistant, mock_bridge_v2: Mock
) -> None:
    """Test if binary_sensor get added/updated from events."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    test_entity_id = "binary_sensor.hue_mocked_device_motion"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake sensor by emitting event
    mock_bridge_v2.api.emit_event("add", FAKE_BINARY_SENSOR)
    await hass.async_block_till_done()

    # the entity should now be available
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "off"

    # test update of entity works on incoming event
    updated_sensor = {**FAKE_BINARY_SENSOR, "motion": {"motion": True}}
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "on"


async def test_grouped_motion_sensor(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test HueGroupedMotionSensor functionality."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    # test grouped motion sensor exists and has correct state
    sensor = hass.states.get("binary_sensor.sensor_group_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.attributes["device_class"] == "motion"

    # test update of grouped motion sensor works on incoming event
    updated_sensor = {
        "id": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
        "type": "grouped_motion",
        "motion": {
            "motion_report": {"changed": "2023-09-23T08:20:51.384Z", "motion": True}
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.sensor_group_motion")
    assert sensor.state == "on"

    # test disabled grouped motion sensor keeps last known state
    disabled_sensor = {
        "id": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
        "type": "grouped_motion",
        "enabled": False,
    }
    mock_bridge_v2.api.emit_event("update", disabled_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.sensor_group_motion")
    assert sensor.state == "off"


async def test_motion_aware_sensor(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test HueMotionAwareSensor functionality."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    # test motion aware sensor exists and has correct state
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.attributes["device_class"] == "motion"

    # test update of motion aware sensor works on incoming event
    updated_sensor = {
        "id": "8b7e4f82-9c3d-4e1a-a5f6-8d9c7b2a3e4f",
        "type": "security_area_motion",
        "motion": {
            "motion": True,
            "motion_valid": True,
            "motion_report": {"changed": "2023-09-23T05:54:08.166Z", "motion": True},
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1")
    assert sensor.state == "on"

    # test name update when motion area configuration name changes
    updated_config = {
        "id": "5e6f7a8b-9c1d-4e2f-b3a4-5c6d7e8f9a0b",
        "type": "motion_area_configuration",
        "name": "Updated Motion Area",
    }
    mock_bridge_v2.api.emit_event("update", updated_config)
    await hass.async_block_till_done()
    # The entity name is derived from the motion area configuration name
    # but the entity ID doesn't change - we just verify the sensor still exists
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1")
    assert sensor is not None
    assert sensor.name == "Updated Motion Area"


async def test_convenience_area_motion_sensor(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test HueConvenienceAreaMotionSensor functionality."""

    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1_convenience_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.attributes["device_class"] == "motion"

    updated_sensor = {
        "id": "4f317b69-9da0-4b4f-84f2-7ca07b9fe345",
        "type": "convenience_area_motion",
        "motion": {
            "motion": True,
            "motion_valid": True,
            "motion_report": {"changed": "2023-09-23T08:13:42.394Z", "motion": True},
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1_convenience_motion")
    assert sensor.state == "on"

    updated_config = {
        "id": "5e6f7a8b-9c1d-4e2f-b3a4-5c6d7e8f9a0b",
        "type": "motion_area_configuration",
        "name": "Updated Motion Area",
    }
    mock_bridge_v2.api.emit_event("update", updated_config)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.motion_aware_sensor_1_convenience_motion")
    assert sensor is not None
    assert sensor.name == "Updated Motion Area Convenience Motion"
