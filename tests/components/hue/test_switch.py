"""Philips Hue switch platform tests for V2 bridge/api."""

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY


async def test_switch(hass, mock_bridge_v2, v2_resources_test_data):
    """Test if (config) switches get created."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 2 entities should be created from test data
    assert len(hass.states.async_all()) == 2

    # test config switch to enable/disable motion sensor
    test_entity = hass.states.get("switch.hue_motion_sensor_motion")
    assert test_entity is not None
    assert test_entity.name == "Hue motion sensor: Motion"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"


async def test_switch_turn_on_service(hass, mock_bridge_v2, v2_resources_test_data):
    """Test calling the turn on service on a switch."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_motion_sensor_motion"

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


async def test_switch_turn_off_service(hass, mock_bridge_v2, v2_resources_test_data):
    """Test calling the turn off service on a switch."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_motion_sensor_motion"

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
    mock_bridge_v2.api.emit_event("update", mock_bridge_v2.mock_requests[0]["json"])
    await hass.async_block_till_done()

    # the switch should now be off
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "off"


async def test_switch_added(hass, mock_bridge_v2):
    """Test new switch added to bridge."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])

    await setup_platform(hass, mock_bridge_v2, "switch")

    test_entity_id = "switch.hue_mocked_device_motion"

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
