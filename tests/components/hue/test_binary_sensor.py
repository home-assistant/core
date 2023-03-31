"""Philips Hue binary_sensor platform tests for V2 bridge/api."""
from homeassistant.core import HomeAssistant

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY


async def test_binary_sensors(
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test if all v2 binary_sensors get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "binary_sensor")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 2 binary_sensors should be created from test data
    assert len(hass.states.async_all()) == 2

    # test motion sensor
    sensor = hass.states.get("binary_sensor.hue_motion_sensor_motion")
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Hue motion sensor Motion"
    assert sensor.attributes["device_class"] == "motion"
    assert sensor.attributes["motion_valid"] is True

    # test entertainment room active sensor
    sensor = hass.states.get(
        "binary_sensor.entertainmentroom_1_entertainment_configuration"
    )
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Entertainmentroom 1: Entertainment Configuration"
    assert sensor.attributes["device_class"] == "running"


async def test_binary_sensor_add_update(hass: HomeAssistant, mock_bridge_v2) -> None:
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
