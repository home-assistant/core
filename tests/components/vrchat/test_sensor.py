"""Test VRChat sensors."""

import asyncio
from types import SimpleNamespace
from typing import cast

from homeassistant.components.vrchat.api_data_types import World
from homeassistant.components.vrchat.const import (
    VRCHAT_USER_STATE_OPTIONS,
    VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState,
)
from homeassistant.components.vrchat.coordinator import VRChatUserDataCoordinator
from homeassistant.components.vrchat.sensor import (
    VRChatUserLocationSensor,
    VRChatUserStateSensor,
    VRChatUserStatusDescriptionSensor,
    VRChatUserStatusSensor,
)
from homeassistant.components.vrchat.utils import VRChatSpecialLocationString
from homeassistant.components.vrchat.world import VRChatWorldData


def test_location_sensor_without_world_metadata() -> None:
    """Test an unresolved world ID has no location state."""
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(
                data={"location": "wrld_test", "worldId": "wrld_test"},
                world=None,
                destination_world=None,
            ),
        )
    )

    assert sensor.native_value is None


def test_location_sensor_options_are_stable_and_unique() -> None:
    """Test location sensor options have a stable order without duplicates."""
    VRChatWorldData.registry.clear()
    VRChatWorldData.get("wrld_first", cast(World, {"name": "World one"}))
    VRChatWorldData.get("wrld_second", cast(World, {"name": "World one"}))
    VRChatWorldData.get("wrld_third", cast(World, {"name": "World two"}))
    VRChatWorldData.get("wrld_offline", cast(World, {"name": "offline"}))
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(data={}, world=None, destination_world=None),
        )
    )

    assert sensor.options == [
        *VRChatSpecialLocationString,
        VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE,
        "World one",
        "World two",
    ]
    assert all(type(option) is str for option in sensor.options)


def test_user_state_options_are_strings() -> None:
    """Test user state options use plain strings."""
    assert all(
        type(option) is str
        for options in (VRCHAT_USER_STATUS_OPTIONS, VRCHAT_USER_STATE_OPTIONS)
        for option in options
    )


def test_state_sensor_returns_strings() -> None:
    """Test state sensor enum values are plain strings."""
    assert (
        type(
            VRChatUserStateSensor.get_state_from_user_data(
                {"location": "offline", "status": "offline"}
            )
        )
        is str
    )
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(
                data={"location": "traveling", "worldId": "traveling"},
                world=None,
                destination_world=None,
            ),
        )
    )

    assert type(sensor.native_value) is str


def test_status_sensor_picture_and_description_icon() -> None:
    """Test status indicator and description icon selection."""
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(
            data={"status": "active", "location": "offline"},
            world=None,
            destination_world=None,
        ),
    )
    status_sensor = VRChatUserStatusSensor(user)
    description_sensor = VRChatUserStatusDescriptionSensor(user)

    assert status_sensor.entity_picture is not None
    assert description_sensor.icon == "mdi:account-badge"

    user.data = {"status": "unknown", "location": "offline"}
    assert status_sensor.entity_picture is None
    assert description_sensor.icon is None


def test_status_sensor_handles_missing_status() -> None:
    """Test status sensors return no value when status is missing."""
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(data={}, world=None, destination_world=None),
    )

    assert VRChatUserStatusSensor(user).entity_picture is None
    assert VRChatUserStatusDescriptionSensor(user).icon is None


def test_sensor_does_not_fall_back_from_empty_top_level_value() -> None:
    """Test an explicitly cleared sensor value does not use stale presence data."""
    user_data = {
        "statusDescription": "",
        "presence": {"statusDescription": "Stale description"},
    }

    assert (
        VRChatUserStatusDescriptionSensor.get_raw_state_from_user_data(user_data) == ""
    )


def test_state_sensor_handles_unknown_presence() -> None:
    """Test state sensor returns no state when presence is unknown."""
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(data={"status": "active"}, world=None, destination_world=None),
    )

    assert VRChatUserStateSensor(user).native_value is None


def test_state_sensor_avatar_fallbacks() -> None:
    """Test state sensor avatar URL fallback order."""
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(
            data={
                "location": "offline",
                "status": "offline",
                "currentAvatarThumbnailImageUrl": "https://example.com/avatar.png",
            },
            world=None,
            destination_world=None,
        ),
    )

    sensor = VRChatUserStateSensor(user)

    assert sensor.entity_picture == "https://example.com/avatar.png"
    user.data["currentAvatarThumbnailImageUrl"] = ""
    user.data["imageUrl"] = "https://example.com/image.png"
    assert sensor.entity_picture == "https://example.com/image.png"


def test_location_sensor_world_attributes() -> None:
    """Test location sensor exposes resolved world metadata."""
    world = SimpleNamespace(data={"id": "wrld_test", "name": "Test world"})
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(
            data={
                "location": "wrld_test:instance",
                "worldId": "wrld_test",
                "instanceId": "instance",
            },
            world=world,
            destination_world=None,
        ),
    )

    sensor = VRChatUserLocationSensor(user)

    assert sensor.extra_state_attributes == {
        "instanceId": "instance",
        "id": "wrld_test",
        "name": "Test world",
    }


async def test_entity_world_data_helpers() -> None:
    """Test world data lookup and update waiting helpers."""
    world_task = asyncio.create_task(asyncio.sleep(0))
    world = SimpleNamespace(data={"name": "Test world"}, task=world_task)
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(
            data={"location": "offline", "status": "offline"},
            world=world,
            destination_world=None,
        ),
    )
    status_sensor = VRChatUserStatusSensor(user)
    location_sensor = VRChatUserLocationSensor(user)

    assert status_sensor.vrchat_user_world_data_get("name") == "Test world"
    assert VRChatUserLocationSensor.should_add_based_on_user_data({})
    world.data = None
    await location_sensor.async_update()
    await world_task
