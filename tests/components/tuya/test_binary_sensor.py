"""Tests for Tuya binary sensor platform."""

from unittest.mock import Mock

from tuya_sharing import DeviceStatusRange

from homeassistant.components.tuya.binary_sensor import generate_binary_sensor_entities


async def test_dehumidifier_binary_sensors(
    mock_tuya_device: Mock, mock_tuya_manager: Mock
) -> None:
    """Test dehumidifier binary sensor."""
    mock_tuya_device.category = "cs"
    mock_tuya_device.status = {
        "switch": True,
        "dehumidify_set_value": 60,
        "child_lock": False,
        "humidity_indoor": 52,
        "countdown_set": "cancel",
        "countdown_left": 0,
        "fault": 0,
    }
    mock_tuya_device.status_range = {
        "switch": DeviceStatusRange(code="switch", type="Boolean", values="{}"),
        "dehumidify_set_value": DeviceStatusRange(
            code="dehumidify_set_value",
            type="Integer",
            values='{"unit":"%","min":35,"max":70,"scale":0,"step":5}',
        ),
        "child_lock": DeviceStatusRange(code="child_lock", type="Boolean", values="{}"),
        "humidity_indoor": DeviceStatusRange(
            code="humidity_indoor",
            type="Integer",
            values='{"unit":"%","min":0,"max":100,"scale":0,"step":1}',
        ),
        "countdown_set": DeviceStatusRange(
            code="countdown_set",
            type="Enum",
            values='{"range":["cancel","1h","2h","3h"]}',
        ),
        "countdown_left": DeviceStatusRange(
            code="countdown_left",
            type="Integer",
            values='{"unit":"h","min":0,"max":24,"scale":0,"step":1}',
        ),
        "fault": DeviceStatusRange(
            code="fault",
            type="Bitmap",
            values='{"label":["tankfull","defrost","E1","E2","L2","L3","L4","wet"]}',
        ),
    }

    entities = list(
        generate_binary_sensor_entities(mock_tuya_device, mock_tuya_manager)
    )
    assert entities[0].entity_description.name == "tankfull"
    assert not entities[0].is_on
    assert entities[1].entity_description.name == "defrost"
    assert not entities[1].is_on
    assert entities[2].entity_description.name == "wet"
    assert not entities[2].is_on

    mock_tuya_device.status["fault"] = 0x1
    entities = list(
        generate_binary_sensor_entities(mock_tuya_device, mock_tuya_manager)
    )
    assert entities[0].entity_description.name == "tankfull"
    assert entities[0].is_on
    assert entities[1].entity_description.name == "defrost"
    assert not entities[1].is_on
    assert entities[2].entity_description.name == "wet"
    assert not entities[2].is_on

    mock_tuya_device.status["fault"] = 0x2
    entities = list(
        generate_binary_sensor_entities(mock_tuya_device, mock_tuya_manager)
    )
    assert entities[0].entity_description.name == "tankfull"
    assert not entities[0].is_on
    assert entities[1].entity_description.name == "defrost"
    assert entities[1].is_on
    assert entities[2].entity_description.name == "wet"
    assert not entities[2].is_on

    mock_tuya_device.status["fault"] = 0x80
    entities = list(
        generate_binary_sensor_entities(mock_tuya_device, mock_tuya_manager)
    )
    assert entities[0].entity_description.name == "tankfull"
    assert not entities[0].is_on
    assert entities[1].entity_description.name == "defrost"
    assert not entities[1].is_on
    assert entities[2].entity_description.name == "wet"
    assert entities[2].is_on

    mock_tuya_device.status["fault"] = 0x83
    entities = list(
        generate_binary_sensor_entities(mock_tuya_device, mock_tuya_manager)
    )
    assert entities[0].entity_description.name == "tankfull"
    assert entities[0].is_on
    assert entities[1].entity_description.name == "defrost"
    assert entities[1].is_on
    assert entities[2].entity_description.name == "wet"
    assert entities[2].is_on
