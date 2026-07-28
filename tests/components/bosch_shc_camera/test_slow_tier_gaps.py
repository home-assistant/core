"""Coverage-gap tests for slow_tier.py's coordinator-facing helpers.

Covers `_compute_cam_context`, `_poll_cam_info_caches` and
`_poll_slow_tier_endpoints` — the pieces of slow_tier.py that read/write
real `BoschCameraCoordinator` state, unlike test_slow_tier.py's pure
per-camera helpers.
"""

import time
from typing import Any, Self
from unittest.mock import MagicMock

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.slow_tier import (
    CamContext,
    _compute_cam_context,
    _poll_cam_info_caches,
    _poll_slow_tier_endpoints,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


@pytest.mark.parametrize(
    ("status", "do_slow", "expected_online", "expected_do_slow_cam"),
    [
        pytest.param("ONLINE", True, True, True, id="online-and-slow-tick"),
        pytest.param("OFFLINE", True, False, True, id="offline-logs-debug-skip"),
        pytest.param("ONLINE", False, True, False, id="fast-tick-no-slow"),
    ],
)
async def test_compute_cam_context_online_and_slow_flags(
    hass: HomeAssistant,
    status: str,
    do_slow: bool,
    expected_online: bool,
    expected_do_slow_cam: bool,
) -> None:
    """`is_online`/`do_slow_cam` are derived from cam status and the tick flag."""
    coordinator = _make_coordinator(hass)
    cam_raw = {"hardwareVersion": "OUTDOOR", "privacyMode": "OFF"}
    data = {CAM_ID: {"status": status}}

    ctx = _compute_cam_context(coordinator, CAM_ID, cam_raw, data, {}, do_slow)

    assert ctx.is_online is expected_online
    assert ctx.do_slow_cam is expected_do_slow_cam


@pytest.mark.parametrize(
    ("hw", "expected_is_gen2"),
    [
        pytest.param("OUTDOOR", False, id="gen1"),
        pytest.param("HOME_Eyes_Outdoor", True, id="gen2"),
    ],
)
async def test_compute_cam_context_generation_detection(
    hass: HomeAssistant, hw: str, expected_is_gen2: bool
) -> None:
    """Hardware generation is derived from `get_model_config`."""
    coordinator = _make_coordinator(hass)
    cam_raw = {
        "hardwareVersion": hw,
        "privacyMode": "ON",
        "featureSupport": {"panLimit": 180, "light": True},
    }
    data = {CAM_ID: {"status": "ONLINE"}}

    ctx = _compute_cam_context(coordinator, CAM_ID, cam_raw, data, {}, True)

    assert ctx.is_gen2 is expected_is_gen2
    assert ctx.privacy_on is True
    assert ctx.pan_limit == 180
    assert ctx.has_light is True


async def test_poll_cam_info_caches_privacy_updates_when_unlocked(
    hass: HomeAssistant,
) -> None:
    """Privacy mode is written from `cam_raw` when no recent write is in flight."""
    coordinator = _make_coordinator(hass)
    cam_raw = {"privacyMode": "ON", "featureSupport": {}, "featureStatus": {}}

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["privacy_mode"] is True


async def test_poll_cam_info_caches_privacy_skipped_while_write_locked(
    hass: HomeAssistant,
) -> None:
    """A recent optimistic privacy write must not be reverted by a stale poll."""
    coordinator = _make_coordinator(hass)
    coordinator.privacy_set_at[CAM_ID] = time.monotonic()
    coordinator.shc_state_cache[CAM_ID] = {
        "device_id": None,
        "camera_light": None,
        "front_light": None,
        "wallwasher": None,
        "front_light_intensity": None,
        "privacy_mode": True,
        "has_light": False,
        "notifications_status": None,
    }
    cam_raw = {"privacyMode": "OFF", "featureSupport": {}, "featureStatus": {}}

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["privacy_mode"] is True


async def test_poll_cam_info_caches_gen2_light_uses_lighting_switch_cache(
    hass: HomeAssistant,
) -> None:
    """Gen2 physical light state comes from `lighting_switch_cache`, not featureStatus."""
    coordinator = _make_coordinator(hass)
    coordinator.lighting_switch_cache[CAM_ID] = {
        "frontLightSettings": {"brightness": 50},
        "topLedLightSettings": {"brightness": 0},
        "bottomLedLightSettings": {"brightness": 20},
    }
    cam_raw = {
        "hardwareVersion": "HOME_Eyes_Outdoor",
        "featureSupport": {"light": True},
        "featureStatus": {"frontIlluminatorInGeneralLightOn": True},
    }

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    cache = coordinator.shc_state_cache[CAM_ID]
    assert cache["front_light"] is True
    assert cache["wallwasher"] is True
    assert cache["camera_light"] is True
    assert cache["front_light_intensity"] == 0.5


async def test_poll_cam_info_caches_gen2_no_lighting_cache_keeps_existing(
    hass: HomeAssistant,
) -> None:
    """Gen2 with no lighting_switch_cache entry yet must not overwrite from featureStatus."""
    coordinator = _make_coordinator(hass)
    coordinator.shc_state_cache[CAM_ID] = {
        "device_id": None,
        "camera_light": True,
        "front_light": None,
        "wallwasher": None,
        "front_light_intensity": None,
        "privacy_mode": None,
        "has_light": True,
        "notifications_status": None,
    }
    cam_raw = {
        "hardwareVersion": "HOME_Eyes_Outdoor",
        "featureSupport": {"light": True},
        "featureStatus": {"frontIlluminatorInGeneralLightOn": True},
    }

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["camera_light"] is True


async def test_poll_cam_info_caches_gen1_light_uses_feature_status(
    hass: HomeAssistant,
) -> None:
    """Gen1 physical light state is read straight from featureStatus."""
    coordinator = _make_coordinator(hass)
    cam_raw = {
        "hardwareVersion": "OUTDOOR",
        "featureSupport": {"light": True},
        "featureStatus": {
            "frontIlluminatorInGeneralLightOn": True,
            "wallwasherInGeneralLightOn": False,
            "frontIlluminatorGeneralLightIntensity": 0.7,
        },
    }

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    cache = coordinator.shc_state_cache[CAM_ID]
    assert cache["camera_light"] is True
    assert cache["front_light"] is True
    assert cache["wallwasher"] is False
    assert cache["front_light_intensity"] == 0.7


async def test_poll_cam_info_caches_no_light_status_defaults_camera_light_none(
    hass: HomeAssistant,
) -> None:
    """No light_on reading at all and no prior cache value yields camera_light=None."""
    coordinator = _make_coordinator(hass)
    cam_raw = {"hardwareVersion": "OUTDOOR", "featureSupport": {}, "featureStatus": {}}

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["camera_light"] is None


async def test_poll_cam_info_caches_notifications_updates_when_unlocked(
    hass: HomeAssistant,
) -> None:
    """Notification status is written when no recent write is in flight."""
    coordinator = _make_coordinator(hass)
    cam_raw = {
        "notificationsEnabledStatus": "ENABLED",
        "featureSupport": {},
        "featureStatus": {},
    }

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["notifications_status"] == "ENABLED"


async def test_poll_cam_info_caches_notifications_skipped_while_write_locked(
    hass: HomeAssistant,
) -> None:
    """A recent optimistic notifications write must not be reverted by a stale poll."""
    coordinator = _make_coordinator(hass)
    coordinator.notif_set_at[CAM_ID] = time.monotonic()
    coordinator.shc_state_cache[CAM_ID] = {
        "device_id": None,
        "camera_light": None,
        "front_light": None,
        "wallwasher": None,
        "front_light_intensity": None,
        "privacy_mode": None,
        "has_light": False,
        "notifications_status": "DISABLED",
    }
    cam_raw = {
        "notificationsEnabledStatus": "ENABLED",
        "featureSupport": {},
        "featureStatus": {},
    }

    _poll_cam_info_caches(coordinator, CAM_ID, cam_raw)

    assert coordinator.shc_state_cache[CAM_ID]["notifications_status"] == "DISABLED"


def _ctx(is_online: bool = True, do_slow_cam: bool = True) -> CamContext:
    return CamContext(
        hw="OUTDOOR",
        is_gen2=False,
        is_online=is_online,
        privacy_on=False,
        do_slow_cam=do_slow_cam,
        pan_limit=0,
        has_light=False,
    )


class _RespCm:
    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        assert self._payload is not None
        return self._payload


class _RaisingCm:
    def __init__(self, err: BaseException) -> None:
        self._err = err

    async def __aenter__(self) -> Self:
        raise self._err

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.mark.parametrize(
    ("do_slow_cam", "is_online"),
    [
        pytest.param(False, True, id="do-slow-cam-false"),
        pytest.param(True, False, id="camera-offline"),
    ],
)
async def test_poll_slow_tier_endpoints_skips_when_not_applicable(
    hass: HomeAssistant, do_slow_cam: bool, is_online: bool
) -> None:
    """Skipped outright when the tick isn't a slow tick or the camera is offline."""
    coordinator = _make_coordinator(hass)
    session = MagicMock()
    session.get = MagicMock(side_effect=AssertionError("must not fetch"))
    data = {CAM_ID: {}}

    await _poll_slow_tier_endpoints(
        coordinator,
        CAM_ID,
        {},
        _ctx(is_online=is_online, do_slow_cam=do_slow_cam),
        data,
        session,
        {},
    )

    assert data[CAM_ID] == {}


async def test_poll_slow_tier_endpoints_dispatches_successful_motion_fetch(
    hass: HomeAssistant,
) -> None:
    """A 200 motion response is dispatched into `data[cam_id]['motion']`."""
    coordinator = _make_coordinator(hass)
    session = MagicMock()
    session.get = MagicMock(return_value=_RespCm(200, {"enabled": True}))
    data = {CAM_ID: {}}

    await _poll_slow_tier_endpoints(coordinator, CAM_ID, {}, _ctx(), data, session, {})

    assert data[CAM_ID]["motion"] == {"enabled": True}


async def test_poll_slow_tier_endpoints_ignores_non_200_response(
    hass: HomeAssistant,
) -> None:
    """A non-200 status must not populate `data[cam_id]`."""
    coordinator = _make_coordinator(hass)
    session = MagicMock()
    session.get = MagicMock(return_value=_RespCm(444, None))
    data = {CAM_ID: {}}

    await _poll_slow_tier_endpoints(coordinator, CAM_ID, {}, _ctx(), data, session, {})

    assert data[CAM_ID] == {}


@pytest.mark.parametrize(
    "err",
    [
        pytest.param(aiohttp.ClientError("boom"), id="client-error"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ValueError("bad json"), id="value-error"),
    ],
)
async def test_poll_slow_tier_endpoints_swallows_fetch_errors(
    hass: HomeAssistant, err: BaseException
) -> None:
    """A fetch-time error must be swallowed, not raised, and not dispatched."""
    coordinator = _make_coordinator(hass)
    session = MagicMock()
    session.get = MagicMock(return_value=_RaisingCm(err))
    data = {CAM_ID: {}}

    await _poll_slow_tier_endpoints(coordinator, CAM_ID, {}, _ctx(), data, session, {})

    assert data[CAM_ID] == {}


async def test_poll_slow_tier_endpoints_skips_gather_exception_result(
    hass: HomeAssistant,
) -> None:
    """An exception type `_fetch` doesn't itself catch still can't crash the tick.

    `asyncio.gather(..., return_exceptions=True)` can hand back a bare
    exception object (not the `(endpoint, status, data)` tuple `_fetch`
    normally returns) for any error type outside its own narrow except
    clause — the dispatch loop must skip that entry instead of crashing.
    """
    coordinator = _make_coordinator(hass)
    session = MagicMock()
    session.get = MagicMock(return_value=_RaisingCm(RuntimeError("unexpected")))
    data = {CAM_ID: {}}

    await _poll_slow_tier_endpoints(coordinator, CAM_ID, {}, _ctx(), data, session, {})

    assert data[CAM_ID] == {}
