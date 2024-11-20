"""Philips Hue binary_sensor platform tests for V2 bridge/api."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY


async def test_binary_sensors(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test if all v2 binary_sensors get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "binary_sensor")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 5 binary_sensors should be created from test data
    assert len(hass.states.async_all()) == 5

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


async def test_binary_sensor_add_update(
    hass: HomeAssistant, mock_bridge_v2: Mock
) -> None:
    """Test if binary_sensor get added/updated from events."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])
    await setup_platform(hass, mock_bridge_v2, "binary_sensor")

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
