"""Philips Hue binary_sensor platform tests for V2 bridge/api."""

from typing import Any
from unittest.mock import Mock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_BINARY_SENSOR, FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY

MOTION_AWARE_ENTITY_ID = "binary_sensor.test_room_test_room_motion_aware_sensor_1"
MOTION_AREA_CONFIGURATION_ID = "5e6f7a8b-9c1d-4e2f-b3a4-5c6d7e8f9a0b"
AREA_MOTION_SERVICE_IDS = {
    "convenience_area_motion": "4f317b69-9da0-4b4f-84f2-7ca07b9fe345",
    "security_area_motion": "8b7e4f82-9c3d-4e1a-a5f6-8d9c7b2a3e4f",
}

MOTION_DETECTED = {
    "motion": True,
    "motion_valid": True,
    "motion_report": {"changed": "2023-09-23T08:20:51.384Z", "motion": True},
}
MOTION_CLEARED = {
    "motion": False,
    "motion_valid": True,
    "motion_report": {"changed": "2023-09-23T08:13:42.394Z", "motion": False},
}
MOTION_INVALID = {
    "motion": False,
    "motion_valid": False,
    "motion_report": {"changed": "2023-09-23T05:54:08.166Z", "motion": False},
}


def area_motion_service(
    service_type: str,
    *,
    enabled: bool = True,
    motion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a service of the MotionAware zone, without `motion` when none is given."""
    service = {
        "id": AREA_MOTION_SERVICE_IDS[service_type],
        "owner": {
            "rid": MOTION_AREA_CONFIGURATION_ID,
            "rtype": "motion_area_configuration",
        },
        "enabled": enabled,
        "type": service_type,
    }
    if motion is not None:
        service["motion"] = motion
    return service


def replace_resources(
    data: JsonArrayType, resources: list[dict[str, Any]]
) -> JsonArrayType:
    """Return the test data with each resource of the same id replaced."""
    replacements = {resource["id"]: resource for resource in resources}
    missing = replacements.keys() - {resource["id"] for resource in data}
    assert not missing, f"resource id(s) not present in the test data: {missing}"
    return [replacements.get(resource["id"], resource) for resource in data]


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
    sensor = hass.states.get(
        "binary_sensor.philips_hue_entertainment_area_entertainmentroom_1"
    )
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Philips hue Entertainment area Entertainmentroom 1"
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
    sensor = hass.states.get(MOTION_AWARE_ENTITY_ID)
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.name == "Test Room Motion Aware Sensor 1"
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
    # NEW: prefer motion_report.motion when present (should turn on even if plain motion
    # is False)
    updated_sensor = {
        **FAKE_BINARY_SENSOR,
        "motion": {
            "motion": False,
            "motion_report": {"changed": "2025-01-01T00:00:00Z", "motion": True},
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    assert hass.states.get(test_entity_id).state == "on"

    # NEW: motion_report False should turn it off (even if plain motion is True)
    updated_sensor = {
        **FAKE_BINARY_SENSOR,
        "motion": {
            "motion": True,
            "motion_report": {"changed": "2025-01-01T00:00:01Z", "motion": False},
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    assert hass.states.get(test_entity_id).state == "off"


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

    # test disabled grouped motion sensor == state unknown
    disabled_sensor = {
        "id": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
        "type": "grouped_motion",
        "enabled": False,
    }
    mock_bridge_v2.api.emit_event("update", disabled_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get("binary_sensor.sensor_group_motion")
    assert sensor.state == "unknown"


async def test_entertainment_active_sensor(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test HueEntertainmentActiveSensor functionality."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    test_entity_id = "binary_sensor.philips_hue_entertainment_area_entertainmentroom_1"
    sensor = hass.states.get(test_entity_id)
    assert sensor is not None
    assert sensor.state == "off"

    # test the sensor turns on once the entertainment area becomes active
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": "c14cf1cf-6c7a-4984-b8bb-c5b71aeb70fc",
            "type": "entertainment_configuration",
            "status": "active",
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(test_entity_id).state == "on"

    # test the name follows a rename of the entertainment area in the Hue app
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": "c14cf1cf-6c7a-4984-b8bb-c5b71aeb70fc",
            "type": "entertainment_configuration",
            "metadata": {"name": "Entertainmentroom 2"},
        },
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get(test_entity_id).name
        == "Philips hue Entertainment area Entertainmentroom 2"
    )


async def test_motion_aware_sensor(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test HueMotionAwareSensor functionality."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    # test motion aware sensor exists and has correct state
    sensor = hass.states.get(MOTION_AWARE_ENTITY_ID)
    assert sensor is not None
    assert sensor.state == "off"
    assert sensor.attributes["device_class"] == "motion"

    # test update of motion aware sensor works on incoming event
    # the zone in the test data has its convenience service enabled, so that is the
    # service reporting its motion
    updated_sensor = {
        "id": "4f317b69-9da0-4b4f-84f2-7ca07b9fe345",
        "type": "convenience_area_motion",
        "motion": {
            "motion": True,
            "motion_valid": True,
            "motion_report": {"changed": "2023-09-23T05:54:08.166Z", "motion": True},
        },
    }
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    sensor = hass.states.get(MOTION_AWARE_ENTITY_ID)
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
    sensor = hass.states.get(MOTION_AWARE_ENTITY_ID)
    assert sensor is not None
    assert sensor.name == "Test Room Updated Motion Area"


@pytest.mark.parametrize(
    ("services", "expected_state"),
    [
        pytest.param(
            [
                area_motion_service("security_area_motion", motion=MOTION_CLEARED),
                area_motion_service("convenience_area_motion", motion=MOTION_DETECTED),
            ],
            "on",
            id="bound_to_lights_reads_convenience",
        ),
        pytest.param(
            [
                area_motion_service("security_area_motion", motion=MOTION_CLEARED),
                area_motion_service(
                    "convenience_area_motion", enabled=False, motion=MOTION_DETECTED
                ),
            ],
            "off",
            id="not_bound_to_lights_reads_security",
        ),
        pytest.param(
            [
                area_motion_service("security_area_motion"),
                area_motion_service("convenience_area_motion", motion=MOTION_DETECTED),
            ],
            "on",
            id="hue_secure_security_without_motion_reads_convenience",
        ),
        pytest.param(
            [
                area_motion_service("security_area_motion", motion=MOTION_INVALID),
                area_motion_service(
                    "convenience_area_motion", enabled=False, motion=MOTION_DETECTED
                ),
            ],
            "unknown",
            id="not_bound_to_lights_without_valid_reading",
        ),
        # a real zone can have its convenience service enabled while only the security
        # service reports, so an enabled service without a reading must not win
        pytest.param(
            [
                area_motion_service("security_area_motion", motion=MOTION_DETECTED),
                area_motion_service("convenience_area_motion", motion=MOTION_INVALID),
            ],
            "on",
            id="falls_back_to_security_when_convenience_has_no_reading",
        ),
    ],
)
async def test_motion_aware_sensor_motion_source(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    services: list[dict[str, Any]],
    expected_state: str,
) -> None:
    """Test the MotionAware sensor reads the zone service that reports motion."""
    # every case gives the service that must be ignored the opposite state, so
    # reading the wrong one results in a state other than the asserted one
    await mock_bridge_v2.api.load_test_data(
        replace_resources(v2_resources_test_data, services)
    )
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == expected_state


async def test_motion_aware_sensor_follows_convenience_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test the MotionAware sensor updates on events of the convenience service."""
    await mock_bridge_v2.api.load_test_data(
        replace_resources(
            v2_resources_test_data,
            [
                area_motion_service("security_area_motion"),
                area_motion_service("convenience_area_motion", motion=MOTION_CLEARED),
            ],
        )
    )
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "off"

    mock_bridge_v2.api.emit_event(
        "update",
        area_motion_service("convenience_area_motion", motion=MOTION_DETECTED),
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "on"


async def test_motion_aware_sensor_follows_security_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test the MotionAware sensor updates on events of the security service."""
    await mock_bridge_v2.api.load_test_data(
        replace_resources(
            v2_resources_test_data,
            [
                area_motion_service("security_area_motion", motion=MOTION_CLEARED),
                area_motion_service(
                    "convenience_area_motion", enabled=False, motion=MOTION_CLEARED
                ),
            ],
        )
    )
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "off"

    mock_bridge_v2.api.emit_event(
        "update",
        area_motion_service("security_area_motion", motion=MOTION_DETECTED),
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "on"


async def test_motion_aware_sensor_without_convenience_resource(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test the MotionAware sensor works when the convenience service is missing."""
    # the zone still lists the service, but the bridge never delivered the resource
    data = replace_resources(
        v2_resources_test_data,
        [area_motion_service("security_area_motion", motion=MOTION_DETECTED)],
    )
    convenience_id = AREA_MOTION_SERVICE_IDS["convenience_area_motion"]
    await mock_bridge_v2.api.load_test_data(
        [resource for resource in data if resource["id"] != convenience_id]
    )
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "on"


@pytest.mark.parametrize(
    ("zone_update", "zone_restore"),
    [
        pytest.param({"enabled": False}, {"enabled": True}, id="zone_switched_off"),
        pytest.param(
            {"health": "not_running"}, {"health": "healthy"}, id="zone_not_running"
        ),
    ],
)
async def test_motion_aware_sensor_zone_not_reporting(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    zone_update: dict[str, Any],
    zone_restore: dict[str, Any],
) -> None:
    """Test the MotionAware sensor reports unknown while its zone is not reporting."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.BINARY_SENSOR)

    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "off"

    # the services keep reporting a valid state while the zone itself does not
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": MOTION_AREA_CONFIGURATION_ID,
            "type": "motion_area_configuration",
            **zone_update,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "unknown"

    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": MOTION_AREA_CONFIGURATION_ID,
            "type": "motion_area_configuration",
            **zone_restore,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_AWARE_ENTITY_ID).state == "off"
