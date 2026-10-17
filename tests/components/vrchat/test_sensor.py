"""Test VRChat sensors."""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from vrchatapi.highlevel import VRChatAccount, WorldCache
from vrchatapi.highlevel.presence import VRChatSpecialLocationString
from vrchatapi.highlevel.types import World

from homeassistant.components.vrchat.const import (
    DOMAIN,
    VRCHAT_USER_STATE_OPTIONS,
    VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState,
)
from homeassistant.components.vrchat.coordinator import (
    VRChatAccountDataCoordinator,
    VRChatUserDataCoordinator,
)
from homeassistant.components.vrchat.sensor import (
    VRChatUserLocationSensor,
    VRChatUserStateSensor,
    VRChatUserStatusDescriptionSensor,
    VRChatUserStatusSensor,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


def test_location_sensor_uses_world_id_for_empty_world_name() -> None:
    """Test an empty world name falls back to the world ID."""
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(
                data={"location": "wrld_test", "worldId": "wrld_test"},
                world=SimpleNamespace(data={"name": ""}),
                destination_world=None,
            ),
        )
    )

    assert sensor.native_value == "wrld_test"


@pytest.mark.parametrize(
    "location",
    [pytest.param("private", id="private"), pytest.param("offline", id="offline")],
)
def test_special_location_overrides_previous_destination(location: str) -> None:
    """An old destination must not hide an explicit private or offline location."""
    world = SimpleNamespace(
        data={
            "name": "Previous map",
            "thumbnailImageUrl": "https://example.com/previous.png",
        }
    )
    user = SimpleNamespace(
        data={"location": "wrld_test:instance", "worldId": "wrld_test"},
        world=world,
        destination_world=world,
    )
    sensor = VRChatUserLocationSensor(cast(VRChatUserDataCoordinator, user))
    assert sensor.native_value == "Previous map"
    assert sensor.entity_picture == "https://example.com/previous.png"

    user.data = {"location": location, "worldId": location, "status": "offline"}
    user.world = None

    assert sensor.native_value == location
    assert sensor.entity_picture is None


def test_location_sensor_options_are_stable_and_unique(
    hass: HomeAssistant,
) -> None:
    """All cached worlds are selectable, with stable ordering and no duplicates."""
    cache = WorldCache(AsyncMock())
    cache.get("wrld_first", cast(World, {"name": "World one"}))
    cache.get("wrld_second", cast(World, {"name": "World one"}))
    cache.get("wrld_third", cast(World, {"name": "World two"}))
    cache.get("wrld_empty", cast(World, {"name": ""}))
    cache.get("wrld_offline", cast(World, {"name": "offline"}))
    account = VRChatAccountDataCoordinator(
        hass, MockConfigEntry(domain=DOMAIN, unique_id="usr_test")
    )
    account.client = cast(VRChatAccount, SimpleNamespace(worlds=cache))
    sensor = VRChatUserLocationSensor(
        cast(
            VRChatUserDataCoordinator,
            SimpleNamespace(
                data={"location": "offline", "status": "offline"},
                world=None,
                destination_world=None,
                account=account,
            ),
        )
    )

    assert sensor.options == [
        *VRChatSpecialLocationString,
        VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE,
        "World one",
        "World two",
        "wrld_empty",
    ]
    assert all(type(option) is str for option in sensor.options)

    cache.get("wrld_third", cast(World, {"name": "Renamed world"}))
    assert sensor.options[-3:] == ["Renamed world", "World one", "wrld_empty"]
    cache.get("wrld_new", cast(World, {"name": "New world"}))
    assert sensor.options[-4:] == [
        "New world",
        "Renamed world",
        "World one",
        "wrld_empty",
    ]


def test_location_follows_travel_and_preserves_pending_name() -> None:
    """Keep the previous name during metadata retries and show travel images."""
    user = SimpleNamespace(
        data={"location": "wrld_first:instance", "worldId": "wrld_first"},
        world=SimpleNamespace(data={"name": "First world"}),
        destination_world=None,
    )
    sensor = VRChatUserLocationSensor(cast(VRChatUserDataCoordinator, user))
    assert sensor.native_value == "First world"

    user.world = SimpleNamespace(data=None)
    assert sensor.native_value == "First world"

    user.data = {"location": "traveling", "worldId": "traveling"}
    user.world = None
    user.destination_world = SimpleNamespace(
        data={"name": "Next world", "thumbnailImageUrl": "https://example.com/next.png"}
    )
    assert sensor.native_value == "traveling"
    assert sensor.entity_picture == "https://example.com/next.png"

    user.data = {"location": "wrld_next:instance", "worldId": "wrld_next"}
    user.world = user.destination_world
    user.destination_world = None
    assert sensor.native_value == "Next world"


def test_state_attributes_exclude_account_details_without_mutating_user() -> None:
    """Filter private and bulky fields while retaining other user metadata."""
    data = {
        "id": "usr_test",
        "displayName": "Test user",
        "bio": "Profile",
        "status": "active",
        "location": "private",
        "customField": "preserved",
        "authToken": "test-token",
        "friendKey": "test-key",
        "friends": ["usr_friend"],
        "activeFriends": ["usr_friend"],
        "onlineFriends": ["usr_friend"],
        "offlineFriends": [],
        "friendGroupNames": ["Private group"],
        "obfuscatedEmail": "t***@example.com",
        "steamDetails": {"steamId": "private-id"},
        "steamId": "private-id",
        "statusHistory": ["old status"],
    }
    original = data.copy()
    sensor = VRChatUserStateSensor(
        cast(VRChatUserDataCoordinator, SimpleNamespace(data=data))
    )

    assert sensor.extra_state_attributes == {
        "id": "usr_test",
        "displayName": "Test user",
        "bio": "Profile",
        "status": "active",
        "location": "private",
        "customField": "preserved",
    }
    assert data == original


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


@pytest.mark.parametrize(
    ("image_data", "expected"),
    [
        pytest.param(
            {"iconUrl": "https://example.com/icon.png"},
            "https://example.com/icon.png",
            id="friend-icon",
        ),
        pytest.param(
            {
                "iconUrl": "https://example.com/icon.png",
                "userIcon": "https://example.com/old-icon.png",
                "currentAvatarImageUrl": "https://example.com/avatar.png",
            },
            "https://example.com/icon.png",
            id="prefer-friend-icon",
        ),
        pytest.param(
            {"iconUrl": "", "userIcon": "https://example.com/user.png"},
            "https://example.com/user.png",
            id="legacy-user-icon",
        ),
        pytest.param(
            {
                "imageUrl": "https://example.com/image.png",
                "currentAvatarThumbnailImageUrl": "https://example.com/thumb.png",
            },
            "https://example.com/image.png",
            id="legacy-image",
        ),
        pytest.param(
            {
                "currentAvatarThumbnailImageUrl": "https://example.com/thumb.png",
                "currentAvatarImageUrl": "https://example.com/avatar.png",
            },
            "https://example.com/thumb.png",
            id="prefer-thumbnail",
        ),
        pytest.param(
            {"iconUrl": "", "currentAvatarImageUrl": "https://example.com/avatar.png"},
            "https://example.com/avatar.png",
            id="avatar-fallback",
        ),
        pytest.param({}, None, id="missing-images"),
        pytest.param(
            {"iconUrl": "", "currentAvatarImageUrl": ""}, None, id="empty-images"
        ),
    ],
)
def test_state_sensor_avatar_fallbacks(
    image_data: dict[str, str], expected: str | None
) -> None:
    """Test state sensor avatar URL fallback order."""
    user = cast(
        VRChatUserDataCoordinator,
        SimpleNamespace(
            data={
                "location": "offline",
                "status": "offline",
                **image_data,
            },
            world=None,
            destination_world=None,
        ),
    )

    sensor = VRChatUserStateSensor(user)

    assert sensor.entity_picture == expected


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
    world = SimpleNamespace(
        data={"name": "Test world"}, task=world_task, get_data=AsyncMock()
    )
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
