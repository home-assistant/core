"""Philips Hue switch platform tests for V2 bridge/api."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY


async def test_switch(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test if (config) switches get created."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 4 entities should be created from test data
    assert len(hass.states.async_all()) == 4

    # test config switch to enable/disable motion sensor
    test_entity = hass.states.get("switch.hue_motion_sensor_motion_sensor_enabled")
    assert test_entity is not None
    assert test_entity.name == "Hue motion sensor Motion sensor enabled"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"

    # test config switch to enable/disable a behavior_instance resource (=builtin automation)
    test_entity = hass.states.get("switch.automation_timer_test")
    assert test_entity is not None
    assert test_entity.name == "Automation: Timer Test"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"


async def test_switch_turn_on_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn on service on a switch."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_motion_sensor_motion_sensor_enabled"

    # call the HA turn_on service
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["enabled"] is True


async def test_switch_turn_off_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn off service on a switch."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_motion_sensor_motion_sensor_enabled"

    # verify the switch is on before we start
    assert hass.states.get(test_entity_id).state == "on"

    # now call the HA turn_off service
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["enabled"] is False

    # Now generate update event by emitting the json we've sent as incoming event
    event = {
        "id": "b6896534-016d-4052-8cb4-ef04454df62c",
        "type": "motion",
        **mock_bridge_v2.mock_requests[0]["json"],
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # the switch should now be off
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "off"


async def test_switch_added(hass: HomeAssistant, mock_bridge_v2: Mock) -> None:
    """Test new switch added to bridge."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_mocked_device_motion_sensor_enabled"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake entity (and attached device and zigbee_connectivity) by emitting events
    mock_bridge_v2.api.emit_event("add", FAKE_BINARY_SENSOR)
    await hass.async_block_till_done()

    # the entity should now be available
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "on"

    # test update
    updated_resource = {**FAKE_BINARY_SENSOR, "enabled": False}
    mock_bridge_v2.api.emit_event("update", updated_resource)
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "off"
