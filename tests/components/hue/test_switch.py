"""Philips Hue switch platform tests for V2 bridge/api."""

from unittest.mock import Mock

import pytest

from homeassistant.components.hue.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import (
    FAKE_BEHAVIOR_INSTANCE,
    FAKE_BEHAVIOR_SCRIPT,
    FAKE_BINARY_SENSOR,
    FAKE_DEVICE,
    FAKE_PRESENCE_MIMICKING_INSTANCE,
    FAKE_PRESENCE_MIMICKING_SCRIPT,
    FAKE_ZIGBEE_CONNECTIVITY,
)

TEST_ROOM_ID = "6ddc9066-7e7d-4a03-a773-c73937968296"


async def test_switch(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test if (config) switches get created."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 5 entities should be created from test data
    assert len(hass.states.async_all()) == 5

    # test config switch to enable/disable motion sensor
    test_entity = hass.states.get("switch.hue_motion_sensor_motion_sensor_enabled")
    assert test_entity is not None
    assert test_entity.name == "Hue motion sensor Motion sensor enabled"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"

    # test config switch to enable/disable a behavior_instance resource (=builtin
    # automation)
    test_entity = hass.states.get("switch.philips_hue_automation_timer_test")
    assert test_entity is not None
    assert test_entity.name == "Philips hue Automation: Timer Test"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"

    # test config switch to enable/disable a MotionAware zone
    test_entity = hass.states.get("switch.test_room_test_room_motionaware")
    assert test_entity is not None
    assert test_entity.name == "Test Room MotionAware"
    assert test_entity.state == "on"
    assert test_entity.attributes["device_class"] == "switch"


async def test_motionaware_switch_device(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the MotionAware switch is attached to the zone device, not the bridge."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    entity_entry = entity_registry.async_get("switch.test_room_test_room_motionaware")
    assert entity_entry is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_ROOM_ID), mock_bridge_v2.config_entry.entry_id
    )
    assert zone_device is not None
    assert entity_entry.device_id == zone_device.id


async def test_switch_turn_on_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn on service on a switch."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

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

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

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


async def test_motionaware_switch_turn_on_off_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test enabling/disabling a MotionAware zone."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    test_entity_id = "switch.test_room_test_room_motionaware"

    # verify the switch is on before we start
    assert hass.states.get(test_entity_id).state == "on"

    # call the HA turn_off service
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # PUT request should have been sent to the motion_area_configuration resource
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert (
        mock_bridge_v2.mock_requests[0]["path"]
        == "clip/v2/resource/motion_area_configuration/"
        "5e6f7a8b-9c1d-4e2f-b3a4-5c6d7e8f9a0b"
    )
    assert mock_bridge_v2.mock_requests[0]["json"]["enabled"] is False

    # Now generate update event by emitting the json we've sent as incoming event
    event = {
        "id": "5e6f7a8b-9c1d-4e2f-b3a4-5c6d7e8f9a0b",
        "type": "motion_area_configuration",
        **mock_bridge_v2.mock_requests[0]["json"],
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # the switch should now be off
    assert hass.states.get(test_entity_id).state == "off"

    # call the HA turn_on service
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["method"] == "put"
    assert mock_bridge_v2.mock_requests[1]["json"]["enabled"] is True


async def test_switch_added(hass: HomeAssistant, mock_bridge_v2: Mock) -> None:
    """Test new switch added to bridge."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    test_entity_id = "switch.hue_mocked_device_motion_sensor_enabled"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake entity (and attached device and zigbee_connectivity) by emitting
    # events
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


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(
            {"name": "Hue Accessories", "category": "accessory"}, id="accessory"
        ),
        pytest.param(
            {"name": "Light state after streaming", "category": "entertainment"},
            id="entertainment",
        ),
        pytest.param({"name": "Old bridge script"}, id="no_category"),
    ],
)
async def test_internal_behavior_instance_not_added(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    metadata: dict,
) -> None:
    """Test internal behavior instances are not exposed as switches.

    The bridge accepts a change to `enabled` on these but keeps running them,
    so a switch for them would silently do nothing. Bridges that do not report
    a category at all are skipped for the same reason.
    """
    internal_script = {**FAKE_BEHAVIOR_SCRIPT, "metadata": metadata}
    await mock_bridge_v2.api.load_test_data(
        [*v2_resources_test_data, internal_script, FAKE_BEHAVIOR_INSTANCE]
    )

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    assert hass.states.get("switch.philips_hue_automation_wall_switch_hallway") is None
    assert hass.states.get("switch.philips_hue_automation_timer_test") is not None
    assert len(hass.states.async_all()) == 5


async def test_internal_behavior_instance_entity_removed(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a previously created entity for an internal instance is removed."""
    # Simulate an entity created with a previous version of the integration
    stale_entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, FAKE_BEHAVIOR_INSTANCE["id"]
    )
    await mock_bridge_v2.api.load_test_data(
        [*v2_resources_test_data, FAKE_BEHAVIOR_SCRIPT, FAKE_BEHAVIOR_INSTANCE]
    )

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    assert entity_registry.async_get(stale_entity.entity_id) is None


@pytest.mark.parametrize(
    ("pm_state", "expected_state"), [("started", "on"), ("stopped", "off")]
)
async def test_presence_mimicking_switch_state(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    pm_state: str,
    expected_state: str,
) -> None:
    """Test the switch follows the run state instead of enabled."""
    instance = {**FAKE_PRESENCE_MIMICKING_INSTANCE, "state": {"pm_state": pm_state}}
    await mock_bridge_v2.api.load_test_data(
        [*v2_resources_test_data, FAKE_PRESENCE_MIMICKING_SCRIPT, instance]
    )

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    test_entity = hass.states.get("switch.philips_hue_automation_mimic_presence")
    assert test_entity is not None
    assert test_entity.state == expected_state


@pytest.mark.parametrize(
    ("service", "expected_trigger"),
    [("turn_on", {"start": {}}), ("turn_off", {"stop": {}})],
)
async def test_presence_mimicking_switch_services(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    service: str,
    expected_trigger: dict,
) -> None:
    """Test the switch starts and stops instead of touching enabled."""
    await mock_bridge_v2.api.load_test_data(
        [
            *v2_resources_test_data,
            FAKE_PRESENCE_MIMICKING_SCRIPT,
            FAKE_PRESENCE_MIMICKING_INSTANCE,
        ]
    )

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": "switch.philips_hue_automation_mimic_presence"},
        blocking=True,
    )

    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"] == {"trigger": expected_trigger}


async def test_regular_automation_switch_uses_enabled(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test an automation without a run state still toggles enabled."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SWITCH)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.philips_hue_automation_timer_test"},
        blocking=True,
    )

    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["json"] == {"enabled": False}
