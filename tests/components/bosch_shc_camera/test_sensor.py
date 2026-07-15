"""Test the Bosch Smart Home Camera sensor platform."""

from datetime import timedelta
import time
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

CAM_OUTDOOR_G1 = "aabbccdd-1122-3344-5566-778899001122"
CAM_INDOOR_G2 = "aabbccdd-1122-3344-5566-778899003344"


def _video_input(
    cam_id: str,
    title: str,
    hardware_version: str,
    *,
    has_light: bool = False,
) -> dict[str, object]:
    """Build a realistic `/v11/video_inputs` list entry."""
    return {
        "id": cam_id,
        "title": title,
        "hardwareVersion": hardware_version,
        "firmwareVersion": "9.40.104",
        "privacyMode": "OFF",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "featureSupport": {"light": has_light},
    }


def _mock_bootstrap(
    aioclient_mock: AiohttpClientMocker,
    video_inputs: list[dict[str, object]],
    *,
    ping_status: int = 200,
    ping_text: str = '"ONLINE"',
) -> None:
    """Register the endpoints every coordinator tick unconditionally needs."""
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", json=video_inputs)
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})
    for cam in video_inputs:
        aioclient_mock.get(
            f"{CLOUD_API}/v11/video_inputs/{cam['id']}/ping",
            status=ping_status,
            text=ping_text,
        )
        # Gen2 lighting/switch is polled every tick (not slow-tier-gated,
        # see `slow_tier._poll_cam_control`) — unconditionally mocked here
        # since our Gen2 fixtures always use hardware string "HOME_Eyes_*".
        if str(cam["hardwareVersion"]).startswith("HOME_Eyes_"):
            aioclient_mock.get(
                f"{CLOUD_API}/v11/video_inputs/{cam['id']}/lighting/switch",
                json={"state": "OFF"},
            )


def _mock_events(
    aioclient_mock: AiohttpClientMocker,
    cam_id: str,
    events: list[dict[str, object]],
) -> None:
    """Register the events-fetch pair a slow-tier `async_refresh()` needs.

    `last_event` is deliberately mocked as a 404 so the coordinator always
    falls through to the full `/v11/events` fetch instead of reusing a
    cached (empty) list — matches `event_polling.py`'s `skip_full_fetch` gate.
    """
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs/{cam_id}/last_event", status=404)
    aioclient_mock.get(
        f"{CLOUD_API}/v11/events?videoInputId={cam_id}&limit=20", json=events
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Every sensor entity created across a Gen1 + a Gen2 Indoor II camera matches the snapshot.

    Only the fast first-tick data (camera list + status) is populated —
    slow-tier caches stay unfetched, so most diagnostic sensors correctly
    snapshot as unavailable/unknown. This still exercises unique_id,
    translation_key, device_class, entity_category and the capability
    gating logic (light feature, Gen2 hardware) for the full platform.
    """
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            "enable_nvr": True,
            "enable_ai_description": True,
            "enable_binary_sensors": False,
        },
    )
    _mock_bootstrap(
        aioclient_mock,
        [
            _video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES", has_light=True),
            _video_input(
                CAM_INDOOR_G2, "Wohnzimmer", "HOME_Eyes_Indoor", has_light=False
            ),
        ],
    )

    with patch(
        "homeassistant.components.bosch_shc_camera.ALL_PLATFORMS", [Platform.SENSOR]
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("has_light", "expect_entity"),
    [
        pytest.param(True, True, id="light-feature-present"),
        pytest.param(False, False, id="light-feature-absent"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_led_dimmer_sensor_gated_on_light_feature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    has_light: bool,
    expect_entity: bool,
) -> None:
    """`BoschLedDimmerSensor` is only registered for cameras with `featureSupport.light`."""
    _mock_bootstrap(
        aioclient_mock,
        [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES", has_light=has_light)],
    )

    await setup_integration(hass, config_entry)

    unique_id = f"bosch_shc_led_dimmer_{CAM_OUTDOOR_G1.lower()}"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert (entity_id is not None) is expect_entity


@pytest.mark.parametrize(
    ("hardware_version", "expect_alarm_state", "expect_ambient_schedule"),
    [
        pytest.param(
            "HOME_Eyes_Indoor", True, False, id="gen2-indoor-ii-alarm-not-ambient"
        ),
        pytest.param(
            "HOME_Eyes_Outdoor", False, True, id="gen2-outdoor-ii-ambient-not-alarm"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gen2_hardware_gates_alarm_state_and_ambient_schedule(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    hardware_version: str,
    expect_alarm_state: bool,
    expect_ambient_schedule: bool,
) -> None:
    """Alarm-state is Indoor-II-only; ambient-light-schedule excludes Indoor II (no RGB lights)."""
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_INDOOR_G2, "Cam", hardware_version)]
    )

    await setup_integration(hass, config_entry)

    alarm_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"bosch_shc_camera_{CAM_INDOOR_G2}_alarm_state"
    )
    ambient_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"bosch_shc_camera_{CAM_INDOOR_G2}_ambient_schedule"
    )
    assert (alarm_id is not None) is expect_alarm_state
    assert (ambient_id is not None) is expect_ambient_schedule


async def test_status_sensor_trouble_disconnect_overrides_online(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A cached `TROUBLE_DISCONNECT` event downgrades an otherwise-online status to `offline`.

    Reproduces the exact case `BoschCameraStatusSensor.native_value` special-cases:
    the cloud's cached "online" ping reading can lag a genuine disconnect that
    already surfaced as a trouble event.
    """
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )
    now_iso = dt_util.utcnow().isoformat()
    _mock_events(
        aioclient_mock,
        CAM_OUTDOOR_G1,
        [{"id": "ev1", "eventType": "TROUBLE_DISCONNECT", "timestamp": now_iso}],
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()  # second tick — runs the events fetch

    state = hass.states.get("sensor.bosch_terrasse_status")
    assert state.state == "offline"


async def test_status_sensor_session_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Bosch's HTTP 444 session-quota response surfaces as `session_limit`, not `unknown`."""
    _mock_bootstrap(
        aioclient_mock,
        [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")],
        ping_status=444,
        ping_text="",
    )

    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.bosch_terrasse_status")
    assert state.state == "session_limit"


async def test_status_sensor_updating_takes_precedence_over_cloud_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An in-progress firmware install reports `updating` even while the cloud still says online."""
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.firmware_cache[CAM_OUTDOOR_G1] = {"updating": True}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.bosch_terrasse_status")
    assert state.state == "updating"


async def test_events_today_counts_only_events_on_local_calendar_date(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Events Today buckets by local calendar date, excluding an event from yesterday."""
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )
    today = dt_util.now()
    yesterday = today - timedelta(days=1)
    _mock_events(
        aioclient_mock,
        CAM_OUTDOOR_G1,
        [
            {
                "id": "ev-today",
                "eventType": "MOVEMENT",
                "timestamp": today.isoformat(),
            },
            {
                "id": "ev-yesterday",
                "eventType": "MOVEMENT",
                "timestamp": yesterday.isoformat(),
            },
        ],
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    state = hass.states.get("sensor.bosch_terrasse_events_today")
    assert state.state == "1"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_zones_sensor_unknown_before_first_fetch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`BoschMotionZonesSensor` reports unavailable (not a confirmed 0) before any of its 3 sources ever succeeded.

    Regression guard for the 2026-07-03 bug-hunt fix noted in `sensor.py`
    (`BoschMotionZonesSensor.native_value`): all 3 caches (`gen2_zones_cache`,
    `cloud_zones_cache`, `rcp_motion_zones_cache`) default to an empty dict
    lookup, so a naive `len(cache.get(cam_id, []))` would report a confirmed
    "0 zones" even before the first successful poll. Only the fast first
    tick runs here — none of the 3 zone endpoints have been fetched yet.
    """
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )

    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.bosch_terrasse_motion_zones")
    assert state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_zones_sensor_reports_zero_once_fetched_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Once a source has definitively been fetched empty, the sensor reports 0 zones, not unavailable."""
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    # Simulate a definitive-but-empty fetch, as the slow-tier dispatcher does
    # for `motion_sensitive_areas` on a Gen1 camera
    # (`coordinator.cloud_zones_cache[cam_id] = []`).
    coordinator.cloud_zones_cache[CAM_OUTDOOR_G1] = []
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.bosch_terrasse_motion_zones")
    assert state.state == "0"


async def test_ambient_light_sensor_ignores_malformed_response(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A malformed-but-200 `ambient_light_sensor_level` body (a JSON list, not an object) is dropped, not crashed on.

    Regression guard for the chaos-fault-injection fix in `slow_tier.py`
    (`_poll_slow_tier_endpoints`, `ambient_light_sensor_level` branch):
    before the `isinstance(ep_data, dict)` guard was added, a non-dict
    200 response raised an uncaught `AttributeError` that killed the
    entire coordinator tick, not just this one sensor.
    """
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )
    _mock_events(aioclient_mock, CAM_OUTDOOR_G1, [])
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs/{CAM_OUTDOOR_G1}/ambient_light_sensor_level",
        json=["unexpected", "list", "shape"],
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()  # runs the slow tier for real

    # The whole tick must survive intact, not just this one cache: an
    # AttributeError raised from inside `_poll_slow_tier_endpoints`'s
    # result-dispatch loop propagates past `asyncio.gather`'s
    # `return_exceptions=True` (that only shields the per-endpoint `_fetch`
    # coroutines, not the dispatch loop itself) and fails the entire
    # coordinator tick — this assertion is what actually distinguishes the
    # guarded from the unguarded behavior; the cache/state assertions below
    # would look identical either way.
    assert coordinator.last_update_success is True
    assert coordinator.ambient_light_cache.get(CAM_OUTDOOR_G1) is None
    state = hass.states.get("sensor.bosch_terrasse_ambient_light")
    assert state.state == "unavailable"


@pytest.mark.parametrize(
    ("live_connections", "stream_warming", "fell_back", "expected"),
    [
        pytest.param({}, False, False, "idle", id="idle"),
        pytest.param({CAM_OUTDOOR_G1: {}}, True, False, "warming_up", id="warming-up"),
        pytest.param({CAM_OUTDOOR_G1: {}}, False, False, "connecting", id="connecting"),
        pytest.param(
            {CAM_OUTDOOR_G1: {"rtspsUrl": "rtsps://127.0.0.1:1/x"}},
            False,
            False,
            "streaming",
            id="streaming",
        ),
        pytest.param(
            {CAM_OUTDOOR_G1: {"rtspsUrl": "rtsps://127.0.0.1:1/x"}},
            False,
            True,
            "streaming_remote",
            id="streaming-remote",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_status_sensor_reflects_coordinator_stream_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    live_connections: dict[str, dict[str, str]],
    stream_warming: bool,
    fell_back: bool,
    expected: str,
) -> None:
    """`BoschStreamStatusSensor` derives its enum purely from coordinator live-session state."""
    _mock_bootstrap(
        aioclient_mock, [_video_input(CAM_OUTDOOR_G1, "Terrasse", "CAMERA_EYES")]
    )

    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.live_connections.update(live_connections)
    if stream_warming:
        coordinator.stream_warming.add(CAM_OUTDOOR_G1)
        coordinator.get_session(CAM_OUTDOOR_G1).warming_started = time.monotonic()
    coordinator.stream_fell_back[CAM_OUTDOOR_G1] = fell_back
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.bosch_terrasse_stream_status")
    assert state.state == expected
