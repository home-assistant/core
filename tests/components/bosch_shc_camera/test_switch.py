"""Test the Bosch Smart Home Camera switch platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import (
    CLOUD_API,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_CLOSE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import TEST_BEARER_TOKEN, TEST_REFRESH_TOKEN, setup_integration

from tests.common import MockConfigEntry, async_mock_service, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

# A single Gen2 Indoor II camera (light + Audio-Plus sound support, part of
# the integrated-alarm hardware family) exercises the widest possible slice
# of switch.py's ~30 entity classes in one setup: light/front-light/
# wallwasher, Gen2-only entities (status LED, motion/ambient light, soft
# fading, intrusion detection, glass-break/fire-alarm, panic alarm), the
# integrated alarm system (arm/mode/pre-alarm), and image rotation (indoor).
CAM_ID = "11112222-3333-4444-5555-666677778888"
CAM_TITLE = "Terrasse"

VIDEO_INPUTS_ONLINE = [
    {
        "id": CAM_ID,
        "title": CAM_TITLE,
        "hardwareVersion": "HOME_Eyes_Indoor",
        "firmwareVersion": "9.40.104",
        "privacyMode": "OFF",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "featureSupport": {"light": True, "sound": True, "panLimit": 0},
    }
]


def _mock_bootstrap_endpoints(
    aioclient_mock: AiohttpClientMocker,
    *,
    video_inputs: list[dict[str, Any]] | None = None,
) -> None:
    """Register the mocks every coordinator first-tick unconditionally needs.

    Mirrors `test_init.py::_mock_bootstrap_endpoints` — kept local to this
    file since the two test modules don't share a common test-only helper
    module today.
    """
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=video_inputs if video_inputs is not None else VIDEO_INPUTS_ONLINE,
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


def _unique_id_entity(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Resolve an entity_id from its switch.py-computed unique_id."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None, f"no entity registered for unique_id={unique_id}"
    return entity_id


def _mark_camera_online(config_entry: MockConfigEntry) -> None:
    """Flip the test camera to ONLINE in the coordinator's live status cache.

    Most `available` properties in switch.py gate on
    `coordinator.is_camera_online(cam_id)`, which reads
    `coordinator.data[cam_id]["status"]` — populated from
    `coordinator.cached_status` on each coordinator tick
    (`event_dispatch.py`). The fast first tick this test suite's bootstrap
    triggers deliberately skips that computation ("Fast first tick —
    skipping events + slow-tier for quick startup"), so every camera starts
    "UNKNOWN"/unavailable and HA's service-call target resolution silently
    drops any entity_id targeting an unavailable entity
    ("Referenced entities ... are missing or not currently available") —
    a service call finding nothing to act on would otherwise look
    identical to (and be mistaken for) a real switch.py bug. Setting both
    the cache and the already-built `coordinator.data` entry directly
    avoids waiting for/forcing another real tick.
    """
    coordinator = config_entry.runtime_data
    coordinator.cached_status[CAM_ID] = "ONLINE"
    coordinator.data.setdefault(CAM_ID, {})["status"] = "ONLINE"


async def _call_switch(hass: HomeAssistant, entity_id: str, *, turn_on: bool) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def _switch_platform_only(hass: HomeAssistant) -> Generator[None]:
    """Load only the switch (+ binary_sensor) platform for this module.

    The camera/image platforms trigger an automatic snapshot pre-fetch
    (`fetch_live_snapshot` -> `open_live_connection`) shortly after setup
    that is unrelated to switch-platform behavior. Since these tests don't
    register a mock for `PUT .../connection`, that background fetch would
    otherwise raise inside `AiohttpClientMocker.match_request` and cascade
    into a real-socket Gen2 LOCAL-RCP fallback attempt, which the test
    harness blocks with `HASocketBlockedError`. Restricting `ALL_PLATFORMS`
    (imported into `__init__.py`'s namespace, patched here) avoids loading
    the camera/image platforms entirely.

    The config entry is explicitly unloaded before the patch is reverted —
    otherwise a later unrelated teardown that unloads any still-loaded
    entries would try to unload the (never-loaded, patched-out) camera
    platform against the real `ALL_PLATFORMS`, raising
    "Config entry was never loaded!".
    """
    with patch(
        "homeassistant.components.bosch_shc_camera.ALL_PLATFORMS", [Platform.SWITCH]
    ):
        yield
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def _route_shc_cloud_session_through_mock(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> Generator[None]:
    """Patch `shc.py`'s own bound `async_get_bosch_cloud_session` reference too.

    `shc.py` does `from .cloud_ssl import async_get_bosch_cloud_session`
    (shc.py:48) — a by-value import that binds its own module-local name at
    import time. The shared `aioclient_mock` fixture (conftest.py) patches
    `cloud_ssl.async_get_bosch_cloud_session` plus the package (`__init__`)
    and `config_flow` re-bindings, but not this one, so every switch write
    that goes through `shc.py`'s cloud setters (privacy/light/notifications)
    was actually hitting the real network — confirmed live: without this
    patch, `test_privacy_mode_turn_on_sends_privacy_on` opened a real
    `socket.socket` and was rejected by the test harness
    (`HASocketBlockedError`). Reuses the same `aioclient_mock` mocker so
    `mock_calls`/registered responses are shared with every other patched
    call site.

    Mirrors conftest.py's own `aioclient_mock` fixture: the created session
    is cached (one per test) and closed on `EVENT_HOMEASSISTANT_CLOSE` —
    without that, each call would mint a fresh, never-closed
    `aiohttp.ClientSession` and the test harness flags it as a leak
    ("Unclosed client session") at teardown.
    """
    cached_session: list[Any] = []

    def _create_session(_hass: HomeAssistant) -> Any:
        if cached_session:
            return cached_session[0]
        session = aioclient_mock.create_session(hass.loop)
        cached_session.append(session)

        async def _close_session(_event: Any) -> None:
            await session.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _close_session)
        return session

    with patch(
        "homeassistant.components.bosch_shc_camera.shc.async_get_bosch_cloud_session",
        side_effect=_create_session,
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A full switch-platform bulk snapshot for a Gen2 Indoor II camera.

    Covers entity creation/naming/attributes for every switch class that a
    single feature-rich camera can register (see CAM_ID's featureSupport +
    hardwareVersion above) in one pass, using Core's standard
    `snapshot_platform` helper (same pattern as reolink/deconz).

    Uses a locally-built config entry (not the shared `config_entry`
    fixture) with `enable_binary_sensors` forced off — `snapshot_platform`
    requires exactly one entity-registry domain, but this integration
    always loads `binary_sensor` alongside `switch` unless that option is
    explicitly disabled (`__init__.py`: `platforms = ["binary_sensor",
    *platforms]` whenever the option defaults True, independent of the
    `ALL_PLATFORMS` restriction the `_switch_platform_only` fixture
    applies for the rest of this module).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": TEST_BEARER_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
        },
        options={**DEFAULT_OPTIONS, "enable_binary_sensors": False},
    )
    _mock_bootstrap_endpoints(aioclient_mock)
    await setup_integration(hass, entry)
    _mark_camera_online(entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


# ─────────────────────────────────────────────────────────────────────────────
# Privacy mode — turn_on / turn_off + outbound PUT body in both directions.
# ─────────────────────────────────────────────────────────────────────────────


async def test_privacy_mode_turn_on_sends_privacy_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning the privacy switch ON PUTs privacyMode=ON to the cloud API."""
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/privacy"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_privacy_{CAM_ID.lower()}"
    )

    await _call_switch(hass, entity_id, turn_on=True)

    assert hass.states.get(entity_id).state == STATE_ON
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert len(put_calls) == 1
    assert put_calls[0][1].path == f"/v11/video_inputs/{CAM_ID}/privacy"
    assert put_calls[0][2] == {"privacyMode": "ON", "durationInSeconds": None}


async def test_privacy_mode_turn_off_sends_privacy_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning the privacy switch OFF PUTs privacyMode=OFF to the cloud API."""
    video_inputs = [dict(VIDEO_INPUTS_ONLINE[0], privacyMode="ON")]
    _mock_bootstrap_endpoints(aioclient_mock, video_inputs=video_inputs)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/privacy"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_privacy_{CAM_ID.lower()}"
    )

    await _call_switch(hass, entity_id, turn_on=False)

    assert hass.states.get(entity_id).state == STATE_OFF
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert len(put_calls) == 1
    assert put_calls[0][2] == {"privacyMode": "OFF", "durationInSeconds": None}


async def test_privacy_mode_write_failure_notifies(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A cloud PUT failure with every fallback exhausted raises a persistent_notification.

    No SHC is configured on this config entry (no shc_host/shc_password in
    `data`) and no LOCAL RCP creds are cached, so both fallback paths in
    `async_cloud_set_privacy_mode` are unreachable and the write should fall
    all the way through to `_notify_write_failed` (shc.py).
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/privacy"
    aioclient_mock.put(url, status=500)
    notifications = async_mock_service(hass, "persistent_notification", "create")

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_privacy_{CAM_ID.lower()}"
    )

    await _call_switch(hass, entity_id, turn_on=True)

    assert len(notifications) == 1
    assert (
        notifications[0].data["notification_id"] == f"bosch_privacy_queued_{CAM_ID[:8]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live stream — opens/tears down a coordinator session, not a plain cloud PUT.
# ─────────────────────────────────────────────────────────────────────────────


async def test_live_stream_switch_turn_on_opens_coordinator_session(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning the live-stream switch ON calls the coordinator's session opener.

    Unlike most switches here, `BoschLiveStreamSwitch` does not PUT a simple
    cloud body — it drives `coordinator.try_live_connection()`, which opens
    a LOCAL/REMOTE RTSP session via the TLS proxy. That machinery is out of
    scope for a switch-platform test, so the coordinator method itself is
    replaced with an `AsyncMock` and we assert the switch drove it correctly.
    """
    _mock_bootstrap_endpoints(aioclient_mock)
    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(entity_registry, f"bosch_shc_live_{CAM_ID.lower()}")
    coordinator = config_entry.runtime_data
    coordinator.try_live_connection = AsyncMock(
        return_value={
            "_connection_type": "REMOTE",
            "rtspsUrl": "rtsps://user:pass@example.invalid:443/x",
        }
    )

    await _call_switch(hass, entity_id, turn_on=True)

    assert hass.states.get(entity_id).state == STATE_ON
    coordinator.try_live_connection.assert_awaited_once_with(CAM_ID)


async def test_live_stream_switch_turn_off_tears_down_session(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning the live-stream switch OFF tears down the coordinator session."""
    _mock_bootstrap_endpoints(aioclient_mock)
    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(entity_registry, f"bosch_shc_live_{CAM_ID.lower()}")
    coordinator = config_entry.runtime_data
    coordinator.try_live_connection = AsyncMock(
        return_value={"_connection_type": "REMOTE", "rtspsUrl": ""}
    )
    coordinator.tear_down_live_stream = AsyncMock()
    # async_turn_off also schedules a real coordinator refresh
    # (`hass.async_create_task(coordinator.async_request_refresh())`) — not
    # relevant to what this test verifies (the teardown call), and a real
    # refresh tick here would run the FULL update (not the fast first-tick
    # bootstrap), which needs many more endpoint mocks than this test
    # registers. No-op it.
    coordinator.async_request_refresh = AsyncMock()
    await _call_switch(hass, entity_id, turn_on=True)
    assert hass.states.get(entity_id).state == STATE_ON

    await _call_switch(hass, entity_id, turn_on=False)

    assert hass.states.get(entity_id).state == STATE_OFF
    coordinator.tear_down_live_stream.assert_awaited_once_with(CAM_ID)


async def test_live_stream_switch_turn_on_blocked_by_privacy_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`async_turn_on` refuses to start while privacy mode is cached ON.

    Calls the entity method directly rather than going through
    `hass.services.async_call` — `BoschLiveStreamSwitch.available` (switch.py)
    ALSO returns False whenever `privacy_mode` is cached True, so a normal
    service call never reaches `async_turn_on` at all: HA's own
    service-target resolution silently drops unavailable entities
    ("Referenced entities ... are missing or not currently available",
    confirmed live — see this file's non-vacuousness notes). That makes the
    explicit `ServiceValidationError` guard inside `async_turn_on`
    (switch.py ~line 414) unreachable via any normal `switch.turn_on`
    service call; this test exercises the guard directly as a white-box
    check of the method's own logic, via the coordinator's
    `live_stream_entities` registry (populated in
    `async_added_to_hass`).
    """
    video_inputs = [dict(VIDEO_INPUTS_ONLINE[0], privacyMode="ON")]
    _mock_bootstrap_endpoints(aioclient_mock, video_inputs=video_inputs)
    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(entity_registry, f"bosch_shc_live_{CAM_ID.lower()}")
    coordinator = config_entry.runtime_data
    coordinator.shc_state_cache.setdefault(CAM_ID, {})["privacy_mode"] = True
    coordinator.try_live_connection = AsyncMock()
    entity = coordinator.live_stream_entities[CAM_ID]

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()

    coordinator.try_live_connection.assert_not_awaited()
    # Unavailable, not "off" — see docstring above: `available` itself
    # returns False while privacy_mode is cached True.
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


# ─────────────────────────────────────────────────────────────────────────────
# Camera light (Gen2: two-endpoint front/topdown fan-out).
# ─────────────────────────────────────────────────────────────────────────────


async def test_camera_light_switch_turn_on_gen2_sends_front_and_topdown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Gen2 camera-light ON PUTs enabled=True to both front and topdown."""
    _mock_bootstrap_endpoints(aioclient_mock)
    front_url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/front"
    topdown_url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/topdown"
    aioclient_mock.put(front_url, status=204)
    aioclient_mock.put(topdown_url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(entity_registry, f"bosch_shc_light_{CAM_ID.lower()}")

    await _call_switch(hass, entity_id, turn_on=True)

    put_bodies = {
        str(c[1]): c[2] for c in aioclient_mock.mock_calls if c[0].lower() == "put"
    }
    assert put_bodies[front_url] == {"enabled": True}
    assert put_bodies[topdown_url] == {"enabled": True}


async def test_camera_light_switch_turn_off_gen2_sends_front_and_topdown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Gen2 camera-light OFF PUTs enabled=False to both front and topdown."""
    _mock_bootstrap_endpoints(aioclient_mock)
    front_url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/front"
    topdown_url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/lighting/switch/topdown"
    aioclient_mock.put(front_url, status=204)
    aioclient_mock.put(topdown_url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    entity_id = _unique_id_entity(entity_registry, f"bosch_shc_light_{CAM_ID.lower()}")

    await _call_switch(hass, entity_id, turn_on=False)

    put_bodies = {
        str(c[1]): c[2] for c in aioclient_mock.mock_calls if c[0].lower() == "put"
    }
    assert put_bodies[front_url] == {"enabled": False}
    assert put_bodies[topdown_url] == {"enabled": False}


# ─────────────────────────────────────────────────────────────────────────────
# Notifications (cloud enable_notifications, three-state aware).
# ─────────────────────────────────────────────────────────────────────────────


async def test_notifications_switch_turn_on_sends_follow_schedule(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning notifications ON always sends FOLLOW_CAMERA_SCHEDULE."""
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/enable_notifications"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    coordinator = config_entry.runtime_data
    # BoschNotificationsSwitch.available requires a cached
    # notifications_status (cloud-only, no is_camera_online dependency) —
    # not populated by the fast first-tick bootstrap this suite uses.
    coordinator.shc_state_cache.setdefault(CAM_ID, {})["notifications_status"] = (
        "ALWAYS_OFF"
    )
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_notifications_{CAM_ID.lower()}"
    )

    await _call_switch(hass, entity_id, turn_on=True)

    assert hass.states.get(entity_id).state == STATE_ON
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert put_calls[-1][2] == {"enabledNotificationsStatus": "FOLLOW_CAMERA_SCHEDULE"}


async def test_notifications_switch_turn_off_sends_always_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Turning notifications OFF sends ALWAYS_OFF."""
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/enable_notifications"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    coordinator = config_entry.runtime_data
    coordinator.shc_state_cache.setdefault(CAM_ID, {})["notifications_status"] = (
        "FOLLOW_CAMERA_SCHEDULE"
    )
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_notifications_{CAM_ID.lower()}"
    )

    await _call_switch(hass, entity_id, turn_on=False)

    assert hass.states.get(entity_id).state == STATE_OFF
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert put_calls[-1][2] == {"enabledNotificationsStatus": "ALWAYS_OFF"}


# ─────────────────────────────────────────────────────────────────────────────
# Gen2 Audio-Plus sound analytics — glass-break / fire-alarm, shared endpoint.
# ─────────────────────────────────────────────────────────────────────────────


async def test_glass_break_detection_switch_turn_on_preserves_fire_alarm(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Toggling glass-break ON sends both fields, preserving fire-alarm's value."""
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/audioDetectionConfig"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    coordinator = config_entry.runtime_data
    # Prime the read-cache the way a slow-tier GET normally would — the
    # write path is a read-modify-write and no-ops on an empty cache.
    coordinator.audio_detection_cache[CAM_ID] = {
        "detectGlassBreak": False,
        "detectFireAlarm": True,
    }
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_camera_{CAM_ID}_glass_break_detection"
    )

    await _call_switch(hass, entity_id, turn_on=True)

    assert hass.states.get(entity_id).state == STATE_ON
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert put_calls[-1][2] == {"detectGlassBreak": True, "detectFireAlarm": True}


async def test_fire_alarm_detection_switch_turn_off_preserves_glass_break(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Toggling fire-alarm OFF sends both fields, preserving glass-break's value."""
    _mock_bootstrap_endpoints(aioclient_mock)
    url = f"{CLOUD_API}/v11/video_inputs/{CAM_ID}/audioDetectionConfig"
    aioclient_mock.put(url, status=204)

    await setup_integration(hass, config_entry)
    _mark_camera_online(config_entry)
    coordinator = config_entry.runtime_data
    coordinator.audio_detection_cache[CAM_ID] = {
        "detectGlassBreak": True,
        "detectFireAlarm": True,
    }
    entity_id = _unique_id_entity(
        entity_registry, f"bosch_shc_camera_{CAM_ID}_fire_alarm_detection"
    )

    await _call_switch(hass, entity_id, turn_on=False)

    assert hass.states.get(entity_id).state == STATE_OFF
    put_calls = [c for c in aioclient_mock.mock_calls if c[0].lower() == "put"]
    assert put_calls[-1][2] == {"detectGlassBreak": True, "detectFireAlarm": False}
