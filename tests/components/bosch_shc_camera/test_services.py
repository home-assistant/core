"""Test the Bosch Smart Home Camera custom services (services.py + __init__.py).

Coverage strategy (per services.yaml's ~21 registered services):
  * every service is registered under the `bosch_shc_camera` domain
  * broad smoke coverage for the simpler read-only/no-op services: they must
    be callable with valid input without raising
  * real behavioral coverage (outbound API call/body assertions) for the
    highest-risk write services: set_motion_zones, set_privacy_masks,
    create_rule, update_rule, share_camera, invite_friend
  * one explicit ServiceValidationError-vs-HomeAssistantError distinction
    test (bad input vs. a downstream cloud failure)

`describe_snapshot` needs a working `ai_task` integration end to end and
`open_live_connection`'s happy path needs a full LOCAL/REMOTE session
negotiation — both are only registration/error-path tested here, not
exercised to a full success response (out of scope per the task brief).
"""

from collections.abc import Iterator
import contextlib

import pytest

from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"
FRIEND_ID = "eeff0011-2233-4455-6677-889900112233"
RULE_ID = "rule-0001"

ALL_SERVICES = [
    "trigger_snapshot",
    "open_live_connection",
    "create_rule",
    "delete_rule",
    "update_rule",
    "set_motion_zones",
    "get_motion_zones",
    "delete_motion_zone",
    "share_camera",
    "get_lighting_schedule",
    "set_lighting_schedule",
    "get_privacy_masks",
    "set_privacy_masks",
    "rename_camera",
    "invite_friend",
    "list_friends",
    "remove_friend",
    "send_event_webhook",
    "migrate_flat_events",
    "delete_event",
    "describe_snapshot",
]


def _mock_bootstrap(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": CAM_ID,
                "title": "Terrasse",
                "hardwareVersion": "CAMERA_EYES",
                "firmwareVersion": "9.40.100",
                "privacyMode": "OFF",
                "featureSupport": {},
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/ping", text='"ONLINE"')


@contextlib.contextmanager
def _assert_raises_nothing() -> Iterator[None]:
    """No-op context manager — documents "must not raise" at call sites."""
    yield


async def test_all_services_registered(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Every service declared in services.yaml (+ describe_snapshot) is registered."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    for service in ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, service), (
            f"service {service} is not registered"
        )


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("trigger_snapshot", {}),
        ("get_motion_zones", {"camera_id": CAM_ID}),
        ("get_privacy_masks", {"camera_id": CAM_ID}),
        ("get_lighting_schedule", {"camera_id": CAM_ID}),
        ("list_friends", {}),
        ("migrate_flat_events", {}),
        ("delete_event", {"camera": "nonexistent_camera_dir"}),
        ("send_event_webhook", {"event_type": "MOVEMENT"}),
    ],
)
async def test_simple_services_smoke(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    service: str,
    data: dict[str, object],
) -> None:
    """Simpler read-only/no-op services are callable with valid input without raising."""
    _mock_bootstrap(aioclient_mock)
    # Read-only GETs used by the notification-style services above.
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/motion_sensitive_areas", json=[]
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/privacy_masks", json=[])
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting_options",
        json={
            "scheduleStatus": "FOLLOW_SCHEDULE",
            "generalLightOnTime": "18:00:00",
            "generalLightOffTime": "23:00:00",
            "darknessThreshold": 0.5,
            "lightOnMotion": False,
            "lightOnMotionFollowUpTimeSeconds": 0,
            "frontIlluminatorInGeneralLightOn": False,
            "wallwasherInGeneralLightOn": False,
            "frontIlluminatorGeneralLightIntensity": 1.0,
        },
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/friends", json=[])
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    # trigger_snapshot fires a background coordinator refresh — mock the
    # bootstrap round again since it re-runs the first-tick endpoint set.
    if service == "trigger_snapshot":
        aioclient_mock.clear_requests()
        _mock_bootstrap(aioclient_mock)

    with _assert_raises_nothing():
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
        await hass.async_block_till_done()


async def test_set_motion_zones_valid_posts_zones(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`set_motion_zones` POSTs the normalized zone list and refreshes the coordinator."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    zones = [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}]
    aioclient_mock.post(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/motion_sensitive_areas",
        status=200,
        json={},
    )

    await hass.services.async_call(
        DOMAIN,
        "set_motion_zones",
        {"camera_id": CAM_ID, "zones": zones},
        blocking=True,
    )
    await hass.async_block_till_done()

    post_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "post"
        and str(call[1]).endswith("/motion_sensitive_areas")
    ]
    assert len(post_calls) == 1
    assert post_calls[0][2] == zones


async def test_set_motion_zones_out_of_range_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A zone coordinate outside 0.0-1.0 is rejected before any HTTP call is made."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_motion_zones",
            {
                "camera_id": CAM_ID,
                "zones": [{"x": 1.5, "y": 0.2, "w": 0.3, "h": 0.4}],
            },
            blocking=True,
        )

    assert not any(
        call[0].lower() == "post" and str(call[1]).endswith("/motion_sensitive_areas")
        for call in aioclient_mock.mock_calls
    )


async def test_set_privacy_masks_valid_posts_masks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`set_privacy_masks` POSTs the normalized mask list and refreshes the coordinator."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    masks = [{"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.5}]
    aioclient_mock.post(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/privacy_masks",
        status=200,
        json={},
    )

    await hass.services.async_call(
        DOMAIN,
        "set_privacy_masks",
        {"camera_id": CAM_ID, "masks": masks},
        blocking=True,
    )
    await hass.async_block_till_done()

    post_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "post" and str(call[1]).endswith("/privacy_masks")
    ]
    assert len(post_calls) == 1
    assert post_calls[0][2] == masks


async def test_set_privacy_masks_missing_field_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A mask missing a required coordinate key is a ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_privacy_masks",
            {"camera_id": CAM_ID, "masks": [{"x": 0.0, "y": 0.0, "w": 1.0}]},
            blocking=True,
        )


async def test_create_rule_posts_schedule_payload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`create_rule` POSTs the expected schedule-rule shape."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.post(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/rules",
        status=201,
        json={"id": RULE_ID},
    )

    await hass.services.async_call(
        DOMAIN,
        "create_rule",
        {
            "camera_id": CAM_ID,
            "name": "Night watch",
            "start_time": "22:00:00",
            "end_time": "06:00:00",
            "weekdays": [0, 1, 2, 3, 4],
            "is_active": True,
        },
        blocking=True,
    )

    post_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "post" and str(call[1]).endswith("/rules")
    ]
    assert len(post_calls) == 1
    body = post_calls[0][2]
    assert body["name"] == "Night watch"
    assert body["isActive"] is True
    assert body["startTime"] == "22:00:00"
    assert body["endTime"] == "06:00:00"
    assert body["weekdays"] == [0, 1, 2, 3, 4]


async def test_create_rule_missing_camera_id_is_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Bad input (no camera_id) raises ServiceValidationError, not a generic error."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "create_rule",
            {"camera_id": ""},
            blocking=True,
        )


async def test_create_rule_cloud_error_is_home_assistant_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A downstream cloud failure (valid input, HTTP 500) raises HomeAssistantError.

    Contrasts with `test_create_rule_missing_camera_id_is_validation_error`:
    same service, but a rejection *after* input validation succeeds must not
    surface as a ServiceValidationError — that class is reserved for bad
    input the user can fix, not for a downstream API failure.
    """
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.post(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/rules",
        status=500,
        json={"error": "internal"},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "create_rule",
            {"camera_id": CAM_ID, "name": "Broken rule"},
            blocking=True,
        )
    assert not isinstance(exc_info.value, ServiceValidationError)


async def test_update_rule_fetches_merges_and_puts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`update_rule` fetches the existing rule, overlays provided fields, and PUTs the merge."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/rules",
        json=[
            {
                "id": RULE_ID,
                "name": "Old name",
                "isActive": False,
                "startTime": "00:00:00",
                "endTime": "23:59:00",
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
            }
        ],
    )
    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/rules/{RULE_ID}",
        status=200,
        json={},
    )

    await hass.services.async_call(
        DOMAIN,
        "update_rule",
        {"camera_id": CAM_ID, "rule_id": RULE_ID, "is_active": True},
        blocking=True,
    )
    await hass.async_block_till_done()

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith(f"/rules/{RULE_ID}")
    ]
    assert len(put_calls) == 1
    body = put_calls[0][2]
    assert body["isActive"] is True
    # Unspecified fields are preserved from the fetched rule (merge, not replace).
    assert body["name"] == "Old name"
    assert body["startTime"] == "00:00:00"


async def test_update_rule_not_found_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Updating a rule_id that doesn't exist on the camera raises ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/rules", json=[])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "update_rule",
            {"camera_id": CAM_ID, "rule_id": "does-not-exist"},
            blocking=True,
        )


async def test_share_camera_puts_shares(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`share_camera` PUTs a shares list with a start/end window sized by `days`."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.put(
        f"{CLOUD_API}/v11/friends/{FRIEND_ID}/share",
        status=200,
        json={},
    )

    await hass.services.async_call(
        DOMAIN,
        "share_camera",
        {"friend_id": FRIEND_ID, "camera_ids": [CAM_ID], "days": 7},
        blocking=True,
    )

    put_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and str(call[1]).endswith("/share")
    ]
    assert len(put_calls) == 1
    shares = put_calls[0][2]
    assert len(shares) == 1
    assert shares[0]["videoInputId"] == CAM_ID
    assert "start" in shares[0]["shareTime"]
    assert "end" in shares[0]["shareTime"]


async def test_share_camera_missing_camera_ids_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`share_camera` without any camera_ids is a ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "share_camera",
            {"friend_id": FRIEND_ID, "camera_ids": []},
            blocking=True,
        )


async def test_invite_friend_posts_invitation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`invite_friend` POSTs the invitation email to /v11/friends."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    aioclient_mock.post(
        f"{CLOUD_API}/v11/friends",
        status=201,
        json={"id": FRIEND_ID},
    )

    await hass.services.async_call(
        DOMAIN,
        "invite_friend",
        {"email": "friend@example.invalid"},
        blocking=True,
    )

    post_calls = [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "post" and str(call[1]).endswith("/v11/friends")
    ]
    assert len(post_calls) == 1
    assert post_calls[0][2]["invitationEmail"] == "friend@example.invalid"


async def test_invite_friend_missing_email_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`invite_friend` without an email is a ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "invite_friend",
            {"email": ""},
            blocking=True,
        )


async def test_invite_friend_network_error_is_home_assistant_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A raised aiohttp.ClientError (not just a non-2xx) is caught and wrapped, not leaked raw."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    from aiohttp import ClientError  # noqa: PLC0415

    aioclient_mock.post(f"{CLOUD_API}/v11/friends", exc=ClientError())

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "invite_friend",
            {"email": "friend@example.invalid"},
            blocking=True,
        )
    assert not isinstance(exc_info.value, ServiceValidationError)


async def test_open_live_connection_missing_camera_id_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`open_live_connection` without camera_id is a ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "open_live_connection",
            {"camera_id": ""},
            blocking=True,
        )


async def test_describe_snapshot_missing_target_raises_validation_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`describe_snapshot` without camera_id or entity_id is a ServiceValidationError."""
    _mock_bootstrap(aioclient_mock)
    assert await async_setup_component(hass, "persistent_notification", {})
    await setup_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "describe_snapshot",
            {},
            blocking=True,
        )
