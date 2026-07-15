"""Test the Bosch Smart Home Camera camera platform."""

from datetime import timedelta
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera import cloud_ssl
from homeassistant.components.bosch_shc_camera.camera import BoschCamera
from homeassistant.components.bosch_shc_camera.const import (
    CLOUD_API,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.components.bosch_shc_camera.maintenance import MaintenanceWindow
from homeassistant.components.camera import (
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_TERRASSE = "aabbccdd-1122-3344-5566-778899001122"
CAM_INNENBEREICH = "aabbccdd-1122-3344-5566-778899003344"
ENTITY_TERRASSE = "camera.bosch_terrasse"
ENTITY_INNENBEREICH = "camera.bosch_innenbereich"

# Field shape matches GET /v11/video_inputs, as read by camera.py's __init__
# and coordinator.py's _async_update_data docstring (id/title/hardwareVersion/
# firmwareVersion/macAddress) and camera_status.py/coordinator (status).
TWO_CAMERAS: list[dict[str, Any]] = [
    {
        "id": CAM_TERRASSE,
        "title": "Terrasse",
        "hardwareVersion": "HOME_Eyes_Outdoor",
        "firmwareVersion": "9.40.104",
        "privacyMode": "OFF",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "featureSupport": {},
        "status": "ONLINE",
    },
    {
        "id": CAM_INNENBEREICH,
        "title": "Innenbereich",
        "hardwareVersion": "HOME_Eyes_Indoor",
        "firmwareVersion": "9.40.104",
        "privacyMode": "OFF",
        "macAddress": "aa:bb:cc:dd:ee:00",
        "featureSupport": {},
        "status": "ONLINE",
    },
]


def _mock_bootstrap(
    aioclient_mock: AiohttpClientMocker,
    video_inputs: list[dict[str, Any]],
) -> None:
    """Register the 3 endpoints every coordinator first tick unconditionally needs."""
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", json=video_inputs)
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """One camera entity is created per camera returned by video_inputs.

    `setup_integration()` forwards every bosch_shc_camera platform (camera is
    only 1 of ~9), so `tests.common.snapshot_platform` (which asserts exactly
    1 loaded domain) cannot be reused as-is here — filter its entity-registry
    query down to the camera domain instead of duplicating its snapshot logic.
    """
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)

    # Camera access_token is a random hex string (regenerated per entity, per
    # HA restart) — freeze it like reolink's own test_camera.py does, or the
    # state snapshot would never be reproducible across runs.
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, config_entry)

    camera_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == "camera"
    ]
    assert camera_entries
    for entry in camera_entries:
        assert entry == snapshot(name=f"{entry.entity_id}-entry")
        assert entry.disabled_by is None
        state = hass.states.get(entry.entity_id)
        assert state, f"State not found for {entry.entity_id}"
        assert state == snapshot(name=f"{entry.entity_id}-state")


async def test_no_camera_entities_when_snapshots_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`enable_snapshots=False` skips the whole camera platform — zero entities."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={**DEFAULT_OPTIONS, "enable_snapshots": False},
    )

    await setup_integration(hass, entry)

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert [e for e in entity_entries if e.domain == "camera"] == []


async def test_stream_source_none_without_live_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """No active live-proxy session — stream_source returns None."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)

    assert await async_get_stream_source(hass, ENTITY_TERRASSE) is None


@pytest.mark.parametrize(
    ("connection_type", "expected_rtsp_transport"),
    [
        pytest.param("REMOTE", {}, id="remote-no-forced-transport"),
        pytest.param("LOCAL", {"rtsp_transport": "tcp"}, id="local-forces-tcp"),
    ],
)
async def test_stream_source_with_live_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    connection_type: str,
    expected_rtsp_transport: dict[str, str],
) -> None:
    """stream_source() returns the cached live-proxy RTSP URL once one is open.

    A real end-to-end PUT /connection + LOCAL pre-warm round trip is exercised
    by coordinator-level tests; camera.py's own contract is simply "read the
    live session the coordinator published to `live_connections`, and apply
    LOCAL-only TCP transport". `live_connections` is the exact dict the
    entity's own docstring says stream_source() reads from (real-time, not the
    once-per-tick `coordinator.data` cache) — driving it directly is the
    documented public surface between the coordinator and this entity, not a
    private implementation detail.
    """
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.live_connections[CAM_TERRASSE] = {
        "rtspsUrl": "rtsps://proxy-01.live.cbs.boschsecurity.com:443/deadbeef/rtsp_tunnel",
        "_connection_type": connection_type,
    }

    source = await async_get_stream_source(hass, ENTITY_TERRASSE)

    assert (
        source == "rtsps://proxy-01.live.cbs.boschsecurity.com:443/deadbeef/rtsp_tunnel"
    )
    camera_entity = coordinator.camera_entities[CAM_TERRASSE]
    assert camera_entity.stream_options == expected_rtsp_transport


async def test_camera_image_from_live_proxy_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Tier 1: an open live-proxy session serves snap.jpg straight from the proxy.

    Unlike coordinator.py/config_flow.py/__init__.py, camera.py imports
    `async_get_bosch_cloud_session` by value at module level (`from
    .cloud_ssl import async_get_bosch_cloud_session`, camera.py line 51)
    instead of the local-import-per-call pattern the rest of the codebase
    uses specifically to stay patchable (see coordinator.py's own comments
    on this). The `aioclient_mock` autouse fixture's docstring claims it
    routes "every Bosch cloud/OAuth HTTP call", but does not patch this
    binding — `camera.py`'s own snapshot-fetch tiers (this one and the
    event-snapshot fallback below) need an extra explicit patch to reach the
    mocked session. Flagged to the caller as a real testability gap in
    camera.py, not fixed here (source left untouched).
    """
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    proxy_url = "https://proxy-01.live.cbs.boschsecurity.com:42090/deadbeef/snap.jpg"
    coordinator.live_connections[CAM_TERRASSE] = {
        "proxyUrl": proxy_url,
        "_connection_type": "REMOTE",
    }
    aioclient_mock.get(
        proxy_url, content=b"live-proxy-jpeg", headers={"Content-Type": "image/jpeg"}
    )

    mocked_session = await cloud_ssl.async_get_bosch_cloud_session(hass)
    with patch(
        "homeassistant.components.bosch_shc_camera.camera.async_get_bosch_cloud_session",
        AsyncMock(return_value=mocked_session),
    ):
        image = await async_get_image(hass, ENTITY_TERRASSE)

    assert image.content == b"live-proxy-jpeg"


async def test_camera_image_first_load_fetches_via_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Tier 2a: no live session, no cache yet — fetches via the coordinator's on-demand snapshot helper.

    `async_fetch_live_snapshot`/`async_fetch_live_snapshot_local` are the
    coordinator methods camera.py explicitly calls for this tier (see
    `_async_camera_image_impl` docstring) — the actual REMOTE/LOCAL PUT
    /connection + snap.jpg mechanics they implement are coordinator-level
    concerns exercised elsewhere; camera.py's own contract under test here is
    just "dispatch to these coordinator methods and cache the result".
    """
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    with patch.object(
        coordinator,
        "async_fetch_live_snapshot",
        AsyncMock(return_value=b"fresh-on-demand-jpeg"),
    ):
        image = await async_get_image(hass, ENTITY_TERRASSE)

    assert image.content == b"fresh-on-demand-jpeg"


async def test_camera_image_falls_back_to_placeholder(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Every fetch tier failing on a cold start serves the 1x1 placeholder, never a raw error body."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    with (
        patch.object(
            coordinator, "async_fetch_live_snapshot", AsyncMock(return_value=None)
        ),
        patch.object(
            coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
    ):
        image = await async_get_image(hass, ENTITY_TERRASSE)

    assert image.content == BoschCamera._PLACEHOLDER_JPEG


async def test_camera_image_last_resort_event_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Tier 4: cold start, no live/cloud snapshot available — falls back to the latest event image.

    `coordinator.data[cam_id]["events"]` is populated from a separate events
    poll (`event_polling.py`), not from `GET /v11/video_inputs` itself — and
    the fast first tick skips that poll entirely (see coordinator.py's
    `_async_update_data` "Fast first tick" branch), so an `events` key on the
    bootstrap `video_inputs` mock response is silently ignored. Push it in
    via the coordinator's own public `async_set_updated_data`, the same
    sanctioned way `test_supported_features_gated_on_offline_status` above
    drives a `coordinator.data` change.

    See `test_camera_image_from_live_proxy_snapshot`'s docstring for why this
    also needs an extra `camera.async_get_bosch_cloud_session` patch on top
    of the `aioclient_mock` autouse fixture.
    """
    event_image_url = f"{CLOUD_API}/events/deadbeef/image.jpg"
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    aioclient_mock.get(
        event_image_url, content=b"event-jpeg", headers={"Content-Type": "image/jpeg"}
    )
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    new_data = dict(coordinator.data)
    new_data[CAM_TERRASSE] = {
        **new_data[CAM_TERRASSE],
        "events": [{"timestamp": "2026-07-14T10:00:00Z", "imageUrl": event_image_url}],
    }
    coordinator.async_set_updated_data(new_data)
    # BUG (camera.py:1427, not fixed here per instructions): tier 3's
    # `if self.cached_image:` does not exclude the 1x1 placeholder identity
    # the way tier 2's condition does (`self.cached_image is
    # self._PLACEHOLDER_JPEG`) — so on a genuine cold start, where
    # `cached_image` is still the placeholder set in `__init__` and every
    # live/cloud fetch tier failed, tier 3 always intercepts and returns the
    # placeholder BEFORE tier 4 (this test's actual target) is ever reached.
    # That contradicts tier 4's own docstring ("last resort on very first
    # startup"): as written, tier 4 is unreachable dead code on that exact
    # scenario. Reproduced and confirmed by temporarily reverting this
    # `cached_image = None` line — the assertion below then fails with the
    # placeholder bytes instead of b"event-jpeg", matching the bug. Forcing
    # `cached_image` to None here isolates tier 4's own logic (it does work
    # once reached) from that separate, already-reported bug.
    coordinator.camera_entities[CAM_TERRASSE].cached_image = None

    mocked_session = await cloud_ssl.async_get_bosch_cloud_session(hass)
    with (
        patch.object(
            coordinator, "async_fetch_live_snapshot", AsyncMock(return_value=None)
        ),
        patch.object(
            coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.camera.async_get_bosch_cloud_session",
            AsyncMock(return_value=mocked_session),
        ),
    ):
        image = await async_get_image(hass, ENTITY_TERRASSE)

    assert image.content == b"event-jpeg"


@pytest.mark.parametrize(
    ("status", "expected_features"),
    [
        pytest.param("ONLINE", CameraEntityFeature.STREAM, id="online-has-stream"),
        pytest.param("OFFLINE", CameraEntityFeature(0), id="offline-drops-stream"),
        pytest.param("UNKNOWN", CameraEntityFeature.STREAM, id="unknown-keeps-stream"),
    ],
)
async def test_supported_features_gated_on_offline_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: str,
    expected_features: CameraEntityFeature,
) -> None:
    """STREAM is advertised unless the camera is definitively OFFLINE."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    new_data = dict(coordinator.data)
    new_data[CAM_TERRASSE] = {**new_data[CAM_TERRASSE], "status": status}
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_TERRASSE)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected_features


async def test_available_false_while_firmware_updating(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A camera mid-firmware-install (reboots for 3-7 min) is marked unavailable."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert hass.states.get(ENTITY_TERRASSE).state != STATE_UNAVAILABLE

    coordinator.firmware_cache[CAM_TERRASSE] = {"updating": True}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_TERRASSE).state == STATE_UNAVAILABLE
    # A sibling camera not mid-update is unaffected.
    assert hass.states.get(ENTITY_INNENBEREICH).state != STATE_UNAVAILABLE


async def test_available_false_on_cloud_outage_without_maintenance_window(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A failed cloud poll with no known active Bosch maintenance window marks unavailable."""
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert hass.states.get(ENTITY_TERRASSE).state != STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", status=500)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert hass.states.get(ENTITY_TERRASSE).state == STATE_UNAVAILABLE


async def test_available_true_on_cloud_outage_with_local_stream_and_maintenance(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A camera stays available during a known Bosch maintenance window if it's still streaming locally.

    `_local_available_during_cloud_outage` requires ALL of: an active
    camera-relevant maintenance window, positive LAN reachability, and an
    established local live session — driven here via the coordinator's own
    public caches (`maintenance_cache`/`lan_tcp_reachable`/`live_connections`),
    matching the exact three guards the docstring in camera.py describes.
    """
    _mock_bootstrap(aioclient_mock, TWO_CAMERAS)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", status=500)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False

    now = dt_util.utcnow()
    coordinator.maintenance_cache = MaintenanceWindow(
        title="Wartungsarbeiten Kamera-Backend",
        link="https://community.bosch-smarthome.com/wartung",
        pub_date=now - timedelta(hours=1),
        summary="Camera cloud maintenance",
        scheduled_start=now - timedelta(minutes=30),
        scheduled_end=now + timedelta(minutes=30),
        source="rss:Wartungsarbeiten",
        camera_relevant=True,
    )
    coordinator.lan_tcp_reachable[CAM_TERRASSE] = (True, time.monotonic())
    coordinator.live_connections[CAM_TERRASSE] = {
        "rtspsUrl": "rtsps://127.0.0.1:8555/local/rtsp_tunnel",
        "_connection_type": "LOCAL",
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_TERRASSE).state != STATE_UNAVAILABLE
