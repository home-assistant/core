"""Test the Bosch Smart Home Camera select platform."""

from typing import Any

import pytest

from homeassistant.components.bosch_shc_camera.const import (
    CLOUD_API,
    CONF_ENABLE_PTZ_CONTROLS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.select import (
    DETECTION_MODE_OPTIONS,
    FCM_PUSH_MODE_OPTIONS,
    MOTION_SENSITIVITY_OPTIONS,
    NVR_MODE_OPTIONS,
    PAN_PRESET_OPTIONS,
    QUALITY_OPTIONS,
    STREAM_MODE_OPTIONS,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_CLOSE,
    SERVICE_SELECT_OPTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import TEST_BEARER_TOKEN, TEST_REFRESH_TOKEN, setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

# Fake camera identifiers — not real Bosch cloud-IDs/MACs.
CAM_ID_GEN2 = "aabbccdd-1122-3344-5566-778899001122"
CAM_ID_PTZ = "11223344-5566-7788-99aa-bbccddeeff00"

# Independently pinned expected preset->degrees mapping (matches Bosch's
# 360 indoor camera pan range) — deliberately NOT imported from select.py's
# PAN_PRESET_ANGLES so a regression there is still caught by the assertions
# below instead of comparing the implementation against itself.
EXPECTED_PAN_PRESET_ANGLES = {
    "home": 0,
    "left": -60,
    "right": 60,
    "back_left": -120,
    "back_right": 120,
}


def _video_inputs_payload() -> list[dict[str, Any]]:
    """Return a fake `/v11/video_inputs` payload: one Gen2 cam, one PTZ-capable Gen1 cam."""
    return [
        {
            "id": CAM_ID_GEN2,
            "title": "Terrasse",
            "hardwareVersion": "HOME_Eyes_Outdoor",
            "firmwareVersion": "9.40.104",
            "privacyMode": "OFF",
            "mac": "aa:bb:cc:dd:ee:ff",
            "featureSupport": {},
        },
        {
            "id": CAM_ID_PTZ,
            "title": "Innenbereich",
            "hardwareVersion": "CAMERA_360",
            "firmwareVersion": "7.91.56",
            "privacyMode": "OFF",
            "mac": "aa:bb:cc:dd:ee:00",
            "featureSupport": {"panLimit": 120},
        },
    ]


def _select_options_entry() -> MockConfigEntry:
    """Return a config entry with every select-gating option turned on."""
    options = dict(DEFAULT_OPTIONS)
    options["enable_nvr"] = True
    options[CONF_ENABLE_PTZ_CONTROLS] = True
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": TEST_BEARER_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
        },
        options=options,
    )


async def _setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> MockConfigEntry:
    """Set up the integration with two cameras and every select entity enabled."""
    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", json=_video_inputs_payload())
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})

    entry = _select_options_entry()
    await setup_integration(hass, entry)
    return entry


async def _setup_with_fcm_enabled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> MockConfigEntry:
    """Set up the integration with `enable_fcm_push` on, real FCM machinery neutralized.

    `enable_fcm_push=True` is required for `BoschFcmPushModeSelect.available`
    to be True (otherwise the entity's state is always STATE_UNAVAILABLE
    regardless of its `current_option`) — but turning it on also makes the
    coordinator's very first tick spawn a real FCM supervisor task
    (`coordinator.py`'s `async_ensure_fcm_supervisor` import, aliased
    `_fcm_async_ensure_supervisor`) that reaches out to Google's real GCM/FCM
    endpoints, which the test sandbox's socket guard rejects. Patched to a
    no-op here since FCM registration/delivery itself is out of scope for
    this select-platform test file.
    """

    async def _noop_supervisor(_coordinator: object) -> None:
        return None

    async def _noop_start(_self: object) -> None:
        return None

    async def _noop_stop(_self: object) -> None:
        return None

    # Two independent call sites both reach real FCM/GCM network I/O for a
    # freshly-added `enable_fcm_push=True` entry: `__init__.py`'s
    # `async_setup_entry` calls `coordinator.async_start_fcm_push()`
    # directly on first load, and `coordinator.py`'s per-tick supervisor
    # heartbeat calls `_fcm_async_ensure_supervisor` separately. Both are
    # patched at the class/module level (not just the instance, which
    # doesn't exist until `setup_integration()` creates the coordinator).
    monkeypatch.setattr(BoschCameraCoordinator, "async_start_fcm_push", _noop_start)
    monkeypatch.setattr(BoschCameraCoordinator, "async_stop_fcm_push", _noop_stop)
    monkeypatch.setattr(
        "homeassistant.components.bosch_shc_camera.coordinator._fcm_async_ensure_supervisor",
        _noop_supervisor,
    )

    aioclient_mock.get(f"{CLOUD_API}/v11/video_inputs", json=_video_inputs_payload())
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})

    options = dict(DEFAULT_OPTIONS)
    options["enable_nvr"] = True
    options[CONF_ENABLE_PTZ_CONTROLS] = True
    options["enable_fcm_push"] = True
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": TEST_BEARER_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
        },
        options=options,
    )
    await setup_integration(hass, entry)
    return entry


def _entity_id(hass: HomeAssistant, unique_id: str) -> str:
    """Look up a select entity_id by its unique_id via the entity registry."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(SELECT_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None, f"no entity registered for unique_id={unique_id}"
    return entity_id


async def _select_option(hass: HomeAssistant, entity_id: str, option: str) -> None:
    """Call select.select_option for entity_id/option and wait for completion."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": option},
        blocking=True,
    )
    await hass.async_block_till_done()


# ── Bulk entity-creation / options-list coverage ────────────────────────────


async def test_video_quality_select_created_with_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The per-camera video-quality select is created with the expected options."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_video_quality")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == QUALITY_OPTIONS
    assert state.state == "auto"


async def test_stream_mode_select_created_with_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The integration-level stream-mode select is created with the expected options."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(hass, "bosch_shc_camera_stream_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == STREAM_MODE_OPTIONS


async def test_fcm_push_mode_select_created_with_options(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The integration-level FCM push-mode select is created with the expected options."""
    await _setup_with_fcm_enabled(hass, aioclient_mock, monkeypatch)

    entity_id = _entity_id(hass, "bosch_shc_camera_fcm_push_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == FCM_PUSH_MODE_OPTIONS


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_nvr_mode_select_created_with_options(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The per-camera Mini-NVR mode select is created with the expected options."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_nvr_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == NVR_MODE_OPTIONS
    assert state.state == "continuous"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensitivity_select_created_with_options(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The per-camera motion-sensitivity select is created with the expected options."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(
        hass, f"bosch_shc_camera_{CAM_ID_GEN2}_motion_sensitivity_select"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == MOTION_SENSITIVITY_OPTIONS


async def test_detection_mode_select_created_only_for_gen2(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The intrusion-detection-mode select exists only for the Gen2 camera."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_detection_mode")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == DETECTION_MODE_OPTIONS

    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            SELECT_DOMAIN,
            DOMAIN,
            f"bosch_shc_camera_{CAM_ID_PTZ}_detection_mode",
        )
        is None
    )


async def test_pan_preset_select_created_only_for_ptz_camera(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The pan-preset select exists only for the PTZ-capable (panLimit>0) camera."""
    await _setup(hass, aioclient_mock)

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_PTZ}_pan_preset")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == PAN_PRESET_OPTIONS

    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            SELECT_DOMAIN,
            DOMAIN,
            f"bosch_shc_camera_{CAM_ID_GEN2}_pan_preset",
        )
        is None
    )


# ── Write-path coverage: select_option for every valid option ──────────────


async def test_video_quality_select_option_every_value(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Selecting every quality option updates the state, with no outbound cloud call.

    No live stream is active in this test (no ``rtspsUrl``/``proxyUrl`` cached),
    so `BoschVideoQualitySelect.async_select_option` never reaches the
    reconnect branch — the quality preference itself is a pure in-memory
    coordinator value, not written to the cloud API.
    """
    await _setup(hass, aioclient_mock)
    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_video_quality")
    baseline_calls = aioclient_mock.call_count

    for option in QUALITY_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option

    assert aioclient_mock.call_count == baseline_calls


async def test_stream_mode_select_option_every_value(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Selecting every stream mode updates both the entity state and the coordinator override."""
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    entity_id = _entity_id(hass, "bosch_shc_camera_stream_mode")
    baseline_calls = aioclient_mock.call_count

    for option in STREAM_MODE_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option
        assert coordinator.stream_type_override == option

    assert aioclient_mock.call_count == baseline_calls


async def test_fcm_push_mode_select_option_every_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting every FCM push mode persists it into config-entry options.

    The actual FCM listener start/stop is out of scope for this platform's
    tests (covered elsewhere) — both are monkeypatched to no-ops so this
    test only exercises the select entity's own option<->state/options
    mapping, not FCM subsystem internals.
    """
    entry = await _setup_with_fcm_enabled(hass, aioclient_mock, monkeypatch)
    coordinator = entry.runtime_data

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(coordinator, "async_stop_fcm_push", _noop)
    monkeypatch.setattr(coordinator, "async_start_fcm_push", _noop)

    entity_id = _entity_id(hass, "bosch_shc_camera_fcm_push_mode")

    for option in FCM_PUSH_MODE_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option
        assert entry.options["fcm_push_mode"] == option


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_nvr_mode_select_option_every_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Selecting every NVR mode updates both entity state and the coordinator override.

    No recorder process is active for either fake camera, so
    `async_select_option`'s "restart if already recording" branch never
    fires and no ffmpeg subprocess is spawned.
    """
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_nvr_mode")
    baseline_calls = aioclient_mock.call_count

    for option in NVR_MODE_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option
        assert coordinator.get_nvr_mode(CAM_ID_GEN2) == option

    assert aioclient_mock.call_count == baseline_calls


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensitivity_select_option_every_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Selecting every motion-sensitivity option issues the correct PUT /motion body."""
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    coordinator.data[CAM_ID_GEN2]["motion"] = {
        "enabled": True,
        "motionAlarmConfiguration": "HIGH",
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    aioclient_mock.put(f"{CLOUD_API}/v11/video_inputs/{CAM_ID_GEN2}/motion", status=200)

    entity_id = _entity_id(
        hass, f"bosch_shc_camera_{CAM_ID_GEN2}_motion_sensitivity_select"
    )

    for option in MOTION_SENSITIVITY_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option

        method, url, data, _headers = aioclient_mock.mock_calls[-1]
        assert method.lower() == "put"
        assert str(url) == f"{CLOUD_API}/v11/video_inputs/{CAM_ID_GEN2}/motion"
        # Expected API value derived independently (`option.upper()`),
        # not by importing select.py's own SENSITIVITY_TO_API mapping —
        # a bug flipping that mapping must still be caught here.
        assert data == {
            "enabled": True,
            "motionAlarmConfiguration": option.upper(),
        }


async def test_detection_mode_select_option_every_value(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Selecting every detection mode issues the correct PUT /intrusionDetectionConfig body."""
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    coordinator.intrusion_config_cache[CAM_ID_GEN2] = {
        "detectionMode": "ALL_MOTIONS",
        "sensitivity": "MEDIUM",
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    aioclient_mock.put(
        f"{CLOUD_API}/v11/video_inputs/{CAM_ID_GEN2}/intrusionDetectionConfig",
        status=200,
    )

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_detection_mode")

    for option in DETECTION_MODE_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option

        method, url, data, _headers = aioclient_mock.mock_calls[-1]
        assert method.lower() == "put"
        assert (
            str(url)
            == f"{CLOUD_API}/v11/video_inputs/{CAM_ID_GEN2}/intrusionDetectionConfig"
        )
        # Expected API value derived independently, not by importing
        # select.py's own DETECTION_TO_API mapping — see the motion-
        # sensitivity test above for why.
        assert data == {
            "detectionMode": option.upper(),
            "sensitivity": "MEDIUM",
        }


async def test_pan_preset_select_option_every_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting every pan preset issues the correct PUT /pan body and updates pan_cache.

    `shc.py` imports `async_get_bosch_cloud_session` by value
    (`from .cloud_ssl import async_get_bosch_cloud_session`) rather than
    accessing it through the `cloud_ssl` module — `conftest.py`'s
    `aioclient_mock` fixture patches `cloud_ssl.async_get_bosch_cloud_session`
    plus two other already-bound names (`__init__.py`/`config_flow.py`) but
    not this one, so `shc.async_cloud_set_pan` (and every other cloud
    setter in shc.py: privacy mode, camera light, front light) bypasses the
    mock and opens a REAL socket. Patched locally here too — see this test
    file's final report for the upstream conftest.py gap.
    """
    shc_session: list[object] = []

    async def _mocked_session(_hass: HomeAssistant) -> object:
        if not shc_session:
            session = aioclient_mock.create_session(hass.loop)
            shc_session.append(session)

            async def _close(_event: object) -> None:
                await session.close()

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _close)
        return shc_session[0]

    monkeypatch.setattr(
        "homeassistant.components.bosch_shc_camera.shc.async_get_bosch_cloud_session",
        _mocked_session,
    )
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    coordinator.pan_cache[CAM_ID_PTZ] = 0
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    aioclient_mock.put(f"{CLOUD_API}/v11/video_inputs/{CAM_ID_PTZ}/pan", status=204)

    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_PTZ}_pan_preset")

    for option in PAN_PRESET_OPTIONS:
        await _select_option(hass, entity_id, option)
        assert hass.states.get(entity_id).state == option
        assert coordinator.pan_cache[CAM_ID_PTZ] == EXPECTED_PAN_PRESET_ANGLES[option]

        method, url, data, _headers = aioclient_mock.mock_calls[-1]
        assert method.lower() == "put"
        assert str(url) == f"{CLOUD_API}/v11/video_inputs/{CAM_ID_PTZ}/pan"
        assert data == {"absolutePosition": EXPECTED_PAN_PRESET_ANGLES[option]}


# ── Garbage-input rejection ─────────────────────────────────────────────────


async def test_select_option_rejects_value_not_in_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unknown option is rejected before the entity is ever called.

    HA-core's own schema validation raises ``ServiceValidationError`` first —
    no state change, no outbound cloud call.
    """
    await _setup(hass, aioclient_mock)
    entity_id = _entity_id(hass, f"bosch_shc_camera_{CAM_ID_GEN2}_video_quality")
    before_state = hass.states.get(entity_id).state
    baseline_calls = aioclient_mock.call_count

    with pytest.raises(ServiceValidationError):
        await _select_option(hass, entity_id, "ultra")

    assert hass.states.get(entity_id).state == before_state
    assert aioclient_mock.call_count == baseline_calls


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_sensitivity_select_option_rejects_garbage(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Garbage input is rejected for a cloud-write-backed select too — no PUT sent."""
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    coordinator.data[CAM_ID_GEN2]["motion"] = {
        "enabled": True,
        "motionAlarmConfiguration": "HIGH",
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = _entity_id(
        hass, f"bosch_shc_camera_{CAM_ID_GEN2}_motion_sensitivity_select"
    )
    before_state = hass.states.get(entity_id).state
    baseline_calls = aioclient_mock.call_count

    with pytest.raises(ServiceValidationError):
        await _select_option(hass, entity_id, "extreme")

    assert hass.states.get(entity_id).state == before_state
    assert aioclient_mock.call_count == baseline_calls
