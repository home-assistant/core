"""Test VRChat sensors."""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from vrchatapi.highlevel import VRChatAccount, VRChatUser, WorldCache
from vrchatapi.highlevel.presence import VRChatSpecialLocationString
from vrchatapi.highlevel.types import World

from homeassistant.components.vrchat.const import (
    DOMAIN,
    VRCHAT_USER_STATE_OPTIONS,
    VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState,
)
from homeassistant.components.vrchat.coordinator import VRChatAccountDataCoordinator
from homeassistant.components.vrchat.sensor import (
    VRChatUserDataSensorEntity,
    VRChatUserLocationSensor,
    VRChatUserStateSensor,
    VRChatUserStatusDescriptionSensor,
    VRChatUserStatusSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

USER_ID = "usr_test"


def _coordinator(hass: HomeAssistant, user: VRChatUser) -> VRChatAccountDataCoordinator:
    """Expose an isolated user snapshot through an account coordinator."""
    coordinator = VRChatAccountDataCoordinator(
        hass, MockConfigEntry(domain=DOMAIN, unique_id=USER_ID)
    )
    coordinator.data = {USER_ID: user}
    return coordinator


def test_location_sensor_without_world_metadata(hass: HomeAssistant) -> None:
    """Test an unresolved world ID has no location state."""
    sensor = VRChatUserLocationSensor(
        _coordinator(
            hass,
            cast(
                VRChatUser,
                SimpleNamespace(
                    data={"location": "wrld_test", "worldId": "wrld_test"},
                    world=None,
                    destination_world=None,
                ),
            ),
        ),
        USER_ID,
    )

    assert sensor.native_value is None


def test_location_sensor_uses_world_id_for_empty_world_name(
    hass: HomeAssistant,
) -> None:
    """Test an empty world name falls back to the world ID."""
    sensor = VRChatUserLocationSensor(
        _coordinator(
            hass,
            cast(
                VRChatUser,
                SimpleNamespace(
                    data={"location": "wrld_test", "worldId": "wrld_test"},
                    world=SimpleNamespace(data={"name": ""}),
                    destination_world=None,
                ),
            ),
        ),
        USER_ID,
    )

    assert sensor.native_value == "wrld_test"


@pytest.mark.parametrize(
    "location",
    [pytest.param("private", id="private"), pytest.param("offline", id="offline")],
)
def test_special_location_overrides_previous_destination(
    hass: HomeAssistant, location: str
) -> None:
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
    sensor = VRChatUserLocationSensor(
        _coordinator(hass, cast(VRChatUser, user)), USER_ID
    )
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
    account.data = {
        USER_ID: cast(
            VRChatUser,
            SimpleNamespace(
                data={"location": "offline", "status": "offline"},
                world=None,
                destination_world=None,
            ),
        )
    }
    sensor = VRChatUserLocationSensor(account, USER_ID)

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


def test_location_follows_travel_and_preserves_pending_name(
    hass: HomeAssistant,
) -> None:
    """Keep the previous name during metadata retries and show travel images."""
    user = SimpleNamespace(
        data={"location": "wrld_first:instance", "worldId": "wrld_first"},
        world=SimpleNamespace(data={"name": "First world"}),
        destination_world=None,
    )
    sensor = VRChatUserLocationSensor(
        _coordinator(hass, cast(VRChatUser, user)), USER_ID
    )
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


def test_state_attributes_exclude_account_details_without_mutating_user(
    hass: HomeAssistant,
) -> None:
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
        _coordinator(hass, cast(VRChatUser, SimpleNamespace(data=data))), USER_ID
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


def test_state_sensor_returns_strings(hass: HomeAssistant) -> None:
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
        _coordinator(
            hass,
            cast(
                VRChatUser,
                SimpleNamespace(
                    data={"location": "traveling", "worldId": "traveling"},
                    world=None,
                    destination_world=None,
                ),
            ),
        ),
        USER_ID,
    )

    assert type(sensor.native_value) is str


def test_status_sensor_picture_and_description_icon(hass: HomeAssistant) -> None:
    """Test status pictures are omitted and description icons are retained."""
    user = cast(
        VRChatUser,
        SimpleNamespace(
            data={"status": "active", "location": "offline"},
            world=None,
            destination_world=None,
        ),
    )
    status_sensor = VRChatUserStatusSensor(_coordinator(hass, user), USER_ID)
    description_sensor = VRChatUserStatusDescriptionSensor(
        _coordinator(hass, user), USER_ID
    )

    assert status_sensor.entity_picture is None
    assert description_sensor.icon == "mdi:account-badge"

    user.data = {"status": "unknown", "location": "offline"}
    assert status_sensor.entity_picture is None
    assert description_sensor.icon is None


def test_status_sensor_handles_missing_status(hass: HomeAssistant) -> None:
    """Test status sensors return no value when status is missing."""
    user = cast(
        VRChatUser,
        SimpleNamespace(data={}, world=None, destination_world=None),
    )

    assert (
        VRChatUserStatusSensor(_coordinator(hass, user), USER_ID).entity_picture is None
    )
    assert (
        VRChatUserStatusDescriptionSensor(_coordinator(hass, user), USER_ID).icon
        is None
    )


def test_sensor_does_not_fall_back_from_empty_top_level_value() -> None:
    """Test an explicitly cleared sensor value does not use stale presence data."""
    user_data = {
        "statusDescription": "",
        "presence": {"statusDescription": "Stale description"},
    }

    assert (
        VRChatUserStatusDescriptionSensor.get_raw_state_from_user_data(user_data) == ""
    )


def test_state_sensor_handles_unknown_presence(hass: HomeAssistant) -> None:
    """Test state sensor returns no state when presence is unknown."""
    user = cast(
        VRChatUser,
        SimpleNamespace(data={"status": "active"}, world=None, destination_world=None),
    )

    assert VRChatUserStateSensor(_coordinator(hass, user), USER_ID).native_value is None


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
    hass: HomeAssistant, image_data: dict[str, str], expected: str | None
) -> None:
    """Test state sensor avatar URL fallback order."""
    user = cast(
        VRChatUser,
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

    sensor = VRChatUserStateSensor(_coordinator(hass, user), USER_ID)

    assert sensor.entity_picture == expected


def test_location_sensor_world_attributes(hass: HomeAssistant) -> None:
    """Test location sensor exposes resolved world metadata."""
    world = SimpleNamespace(data={"id": "wrld_test", "name": "Test world"})
    user = cast(
        VRChatUser,
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

    sensor = VRChatUserLocationSensor(_coordinator(hass, user), USER_ID)

    assert sensor.extra_state_attributes == {
        "instanceId": "instance",
        "id": "wrld_test",
        "name": "Test world",
    }


async def test_entity_world_data_helpers(hass: HomeAssistant) -> None:
    """Test world data lookup and update waiting helpers."""
    world_task = asyncio.create_task(asyncio.sleep(0))
    world = SimpleNamespace(
        data={"name": "Test world"}, task=world_task, get_data=AsyncMock()
    )
    user = cast(
        VRChatUser,
        SimpleNamespace(
            data={"location": "offline", "status": "offline"},
            world=world,
            destination_world=None,
        ),
    )
    status_sensor = VRChatUserStatusSensor(_coordinator(hass, user), USER_ID)
    location_sensor = VRChatUserLocationSensor(_coordinator(hass, user), USER_ID)

    assert status_sensor.vrchat_user_world_data_get("name") == "Test world"
    assert VRChatUserLocationSensor.should_add_based_on_user_data({})
    world.data = None
    await location_sensor.async_update()
    await world_task


@pytest.mark.parametrize(
    "sensor_class",
    [
        pytest.param(VRChatUserStatusSensor, id="status"),
        pytest.param(VRChatUserStatusDescriptionSensor, id="description"),
        pytest.param(VRChatUserStateSensor, id="state"),
        pytest.param(VRChatUserLocationSensor, id="location"),
    ],
)
def test_user_access_requires_a_live_coordinator_entry(
    hass: HomeAssistant, sensor_class: type[VRChatUserDataSensorEntity]
) -> None:
    """User access enforces the lifecycle invariant without a fallback snapshot."""
    coordinator = _coordinator(
        hass,
        cast(
            VRChatUser,
            SimpleNamespace(
                data={"status": "active", "location": "offline"},
                world=None,
                destination_world=None,
            ),
        ),
    )
    sensor = sensor_class(coordinator, USER_ID)
    unique_id = sensor.unique_id
    assert sensor.device_info["identifiers"] == {(DOMAIN, f"{USER_ID}:{USER_ID}")}
    coordinator.data.clear()

    assert not sensor.available
    with pytest.raises(KeyError, match=USER_ID):
        _ = sensor.user
    assert sensor.unique_id == unique_id


@pytest.mark.parametrize(
    ("sensor_class", "key", "translation_key"),
    [
        pytest.param(VRChatUserStatusSensor, "status", "status", id="status"),
        pytest.param(
            VRChatUserStatusDescriptionSensor,
            "statusDescription",
            "status_description",
            id="description",
        ),
        pytest.param(VRChatUserStateSensor, "state", "state", id="state"),
        pytest.param(VRChatUserLocationSensor, "location", "location", id="location"),
    ],
)
def test_sensor_identity_and_translation_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    sensor_class: type[VRChatUserDataSensorEntity],
    key: str,
    translation_key: str,
) -> None:
    """Keep account-scoped IDs stable independently of names and translation keys."""
    user = cast(
        VRChatUser,
        SimpleNamespace(
            data={
                "displayName": "Initial name",
                "status": "active",
                "statusDescription": "Hello",
                "location": "private",
            },
            world=None,
            destination_world=None,
        ),
    )
    coordinator = _coordinator(hass, user)
    sensor = sensor_class(coordinator, USER_ID)
    expected_unique_id = f"{key}.{USER_ID}:{USER_ID}"

    assert sensor.unique_id == expected_unique_id
    assert sensor.entity_description.key == key
    assert sensor.translation_key == translation_key
    assert sensor.device_info["identifiers"] == {(DOMAIN, f"{USER_ID}:{USER_ID}")}
    assert (
        sensor.device_info["configuration_url"]
        == f"https://vrchat.com/home/user/{USER_ID}"
    )

    user.data["displayName"] = "Renamed user"
    assert sensor.unique_id == expected_unique_id
    assert sensor_class(coordinator, USER_ID).unique_id == expected_unique_id

    coordinator.data.clear()
    assert not sensor.available
    assert sensor.unique_id == expected_unique_id
    coordinator.data[USER_ID] = user
    assert sensor_class(coordinator, USER_ID).unique_id == expected_unique_id

    other_entry = MockConfigEntry(domain=DOMAIN, unique_id="usr_other_account")
    other_entry.add_to_hass(hass)
    other_parent_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "usr_other_account:usr_other_account")},
    )
    other_account = VRChatAccountDataCoordinator(hass, other_entry)
    other_account.data = {USER_ID: user}
    other_sensor = sensor_class(other_account, USER_ID)
    assert other_sensor.unique_id == f"{key}.usr_other_account:{USER_ID}"
    assert other_sensor.unique_id != sensor.unique_id
    assert other_sensor.device_info["via_device_id"] == other_parent_device.id
    assert other_sensor.device_info["identifiers"] == {
        (DOMAIN, f"usr_other_account:{USER_ID}")
    }


@pytest.mark.parametrize(
    ("sensor_class", "expected_state"),
    [
        pytest.param(VRChatUserStatusSensor, "busy", id="status"),
        pytest.param(
            VRChatUserStatusDescriptionSensor, "New description", id="description"
        ),
        pytest.param(VRChatUserStateSensor, "busy", id="state"),
        pytest.param(VRChatUserLocationSensor, "private", id="location"),
    ],
)
def test_removed_then_readded_user_uses_fresh_snapshot(
    hass: HomeAssistant,
    sensor_class: type[VRChatUserDataSensorEntity],
    expected_state: str,
) -> None:
    """Re-adding the same ID cannot retain a removed user's snapshot."""
    original_user = cast(
        VRChatUser,
        SimpleNamespace(
            data={
                "status": "active",
                "statusDescription": "Old",
                "location": "private",
            },
            world=None,
            destination_world=None,
        ),
    )
    coordinator = _coordinator(hass, original_user)
    coordinator.client = cast(VRChatAccount, SimpleNamespace(available=True))
    sensor = sensor_class(coordinator, USER_ID)
    unique_id = sensor.unique_id
    assert sensor.available
    assert sensor.user is original_user

    coordinator.data.clear()
    assert not sensor.available
    with pytest.raises(KeyError, match=USER_ID):
        _ = sensor.user

    replacement_user = cast(
        VRChatUser,
        SimpleNamespace(
            data={
                "status": "busy",
                "statusDescription": "New description",
                "location": "private",
            },
            world=None,
            destination_world=None,
        ),
    )
    coordinator.data[USER_ID] = replacement_user
    assert sensor.available
    assert sensor.user is replacement_user
    assert sensor.native_value == expected_state
    assert sensor.unique_id == unique_id
