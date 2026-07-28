"""Tests for camera_status.py's `_check_one_camera_status`/`poll_statuses`.

`_check_one_camera_status`/`poll_statuses` take the coordinator as a plain
parameter (not an entity), so a `SimpleNamespace`/`MagicMock` stub
coordinator is the established pattern (mirrors test_camera_list.py) —
not the Entity-construction-bypass anti-pattern flagged elsewhere on this
PR.
"""

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.bosch_shc_camera.camera_status import (
    _check_one_camera_status,
    poll_statuses,
)

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _resp_cm(status: int, text: str = "", json_data: object = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.json = AsyncMock(return_value=json_data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_coordinator(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "should_check_status": MagicMock(return_value=True),
        "async_local_tcp_ping": AsyncMock(return_value=False),
        "cached_status": {},
        "per_cam_status_at": {},
        "offline_since": {},
        "commissioned_cache": {},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── _check_one_camera_status ────────────────────────────────────────────────


async def test_skips_check_when_not_due_returns_cached_status() -> None:
    """`should_check_status` gating this camera returns the cached status without any I/O."""
    coordinator = _make_coordinator(
        should_check_status=MagicMock(return_value=False),
        cached_status={CAM_ID: "ONLINE"},
    )
    session = MagicMock()

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "ONLINE")
    session.get.assert_not_called()


async def test_local_tcp_ping_online_skips_cloud_check() -> None:
    """A reachable LAN TCP ping short-circuits straight to ONLINE, no cloud call."""
    coordinator = _make_coordinator(async_local_tcp_ping=AsyncMock(return_value=True))
    coordinator.offline_since[CAM_ID] = 42.0
    session = MagicMock()

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "ONLINE")
    assert coordinator.per_cam_status_at[CAM_ID] == 100.0
    assert CAM_ID not in coordinator.offline_since
    session.get.assert_not_called()


@pytest.mark.parametrize(
    ("ping_text", "expected_status"),
    [
        pytest.param('"ONLINE"', "ONLINE", id="online"),
        pytest.param('"OFFLINE"', "OFFLINE", id="offline"),
        pytest.param('"UPDATING_9.40.104"', "UPDATING", id="updating"),
    ],
)
async def test_cloud_ping_200_maps_status(ping_text: str, expected_status: str) -> None:
    """A 200 `/ping` response maps directly to ONLINE/OFFLINE/UPDATING."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(200, text=ping_text))

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, expected_status)
    session.get.assert_called_once()  # commissioned fallback not reached


async def test_cloud_ping_444_session_limit_skips_commissioned_fallback() -> None:
    """A 444 (session-quota) response is SESSION_LIMIT — no commissioned fallback needed."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(444))

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "SESSION_LIMIT")
    session.get.assert_called_once()


async def test_cloud_ping_network_error_falls_back_to_commissioned() -> None:
    """A ping network error falls through to the `/commissioned` fallback."""
    coordinator = _make_coordinator()
    session = MagicMock()

    def _raise(*_a: object, **_k: object) -> None:
        raise TimeoutError

    session.get = MagicMock(
        side_effect=[
            MagicMock(
                __aenter__=AsyncMock(side_effect=TimeoutError), __aexit__=AsyncMock()
            ),
            _resp_cm(200, json_data={"connected": True, "commissioned": True}),
        ]
    )

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "ONLINE")
    assert session.get.call_count == 2


async def test_commissioned_connected_and_commissioned_is_online() -> None:
    """`/commissioned` reporting connected+commissioned reads as ONLINE."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _resp_cm(500),  # ping fails (non-200, non-444) -> ping_ok stays False
            _resp_cm(200, json_data={"connected": True, "commissioned": True}),
        ]
    )

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "ONLINE")
    assert coordinator.commissioned_cache[CAM_ID] == {
        "connected": True,
        "commissioned": True,
    }


async def test_commissioned_configured_only_is_offline() -> None:
    """`/commissioned` reporting only `configured` (not connected) reads as OFFLINE."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[_resp_cm(500), _resp_cm(200, json_data={"configured": True})]
    )

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "OFFLINE")


async def test_commissioned_444_session_limit() -> None:
    """A 444 on `/commissioned` is also SESSION_LIMIT."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(side_effect=[_resp_cm(500), _resp_cm(444)])

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "SESSION_LIMIT")


async def test_commissioned_error_is_swallowed_and_keeps_seeded_status() -> None:
    """A `/commissioned` network error is swallowed, keeping the seeded cached status."""
    coordinator = _make_coordinator(cached_status={CAM_ID: "OFFLINE"})
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _resp_cm(500),
            MagicMock(
                __aenter__=AsyncMock(side_effect=ValueError), __aexit__=AsyncMock()
            ),
        ]
    )

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "OFFLINE")


@pytest.mark.parametrize(
    ("status", "already_offline_since", "expect_offline_since_set"),
    [
        pytest.param("OFFLINE", None, True, id="offline-newly-tracked"),
        pytest.param("OFFLINE", 5.0, True, id="offline-already-tracked-unchanged"),
        pytest.param("ONLINE", 5.0, False, id="online-clears-tracking"),
    ],
)
async def test_offline_since_tracking(
    status: str, already_offline_since: float | None, expect_offline_since_set: bool
) -> None:
    """`offline_since` is set once on OFFLINE/UPDATING and cleared once healthy again."""
    coordinator = _make_coordinator()
    if already_offline_since is not None:
        coordinator.offline_since[CAM_ID] = already_offline_since
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(200, text=f'"{status}"'))

    await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    if expect_offline_since_set:
        assert CAM_ID in coordinator.offline_since
        if already_offline_since is not None:
            assert coordinator.offline_since[CAM_ID] == already_offline_since
    else:
        assert CAM_ID not in coordinator.offline_since


async def test_session_limit_triggers_quota_handler_via_spawn_tracked() -> None:
    """A SESSION_LIMIT status fires the quota handler through `spawn_tracked`."""
    handle_quota = AsyncMock()

    def _spawn_tracked_close(
        coro: Coroutine[Any, Any, Any], **_kwargs: object
    ) -> MagicMock:
        coro.close()  # never actually scheduled here, avoid a leaked-coroutine warning
        return MagicMock()

    coordinator = _make_coordinator(
        spawn_tracked=MagicMock(side_effect=_spawn_tracked_close),
        _async_handle_session_quota_hit=handle_quota,
    )
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(444))

    await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    coordinator.spawn_tracked.assert_called_once()
    _, call_kwargs = coordinator.spawn_tracked.call_args
    assert call_kwargs["name"] == f"bosch_shc_camera_session_quota_{CAM_ID[:8]}"


async def test_session_limit_without_quota_handler_does_not_crash() -> None:
    """A coordinator without `_async_handle_session_quota_hit` (getattr default) is safe."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(444))

    cam_id, status = await _check_one_camera_status(
        coordinator, CAM_ID, session, {}, now=100.0, interval_status=60
    )

    assert (cam_id, status) == (CAM_ID, "SESSION_LIMIT")


# ── poll_statuses ────────────────────────────────────────────────────────────


async def test_poll_statuses_returns_true_and_updates_cached_status() -> None:
    """A normal successful pass updates `cached_status` and reports checked=True."""
    coordinator = _make_coordinator(async_local_tcp_ping=AsyncMock(return_value=True))

    result = await poll_statuses(
        coordinator, [CAM_ID], MagicMock(), {}, now=100.0, opts={"interval_status": 60}
    )

    assert result is True
    assert coordinator.cached_status[CAM_ID] == "ONLINE"


async def test_poll_statuses_skips_exception_results_but_still_reports_checked() -> (
    None
):
    """One camera's coroutine raising must not abort the others' processing."""
    coordinator = _make_coordinator(
        async_local_tcp_ping=AsyncMock(side_effect=RuntimeError("boom"))
    )

    result = await poll_statuses(
        coordinator, [CAM_ID], MagicMock(), {}, now=100.0, opts={"interval_status": 60}
    )

    assert result is False
    assert CAM_ID not in coordinator.cached_status


async def test_poll_statuses_mixed_exception_and_success() -> None:
    """A mix of one failing and one succeeding camera still reports checked=True overall."""
    good_cam = "11111111-1111-1111-1111-111111111111"
    bad_cam = "22222222-2222-2222-2222-222222222222"

    async def _ping(cam_id: str) -> bool:
        if cam_id == bad_cam:
            raise RuntimeError("boom")
        return True

    coordinator = _make_coordinator(async_local_tcp_ping=_ping)

    result = await poll_statuses(
        coordinator,
        [good_cam, bad_cam],
        MagicMock(),
        {},
        now=100.0,
        opts={"interval_status": 60},
    )

    assert result is True
    assert coordinator.cached_status[good_cam] == "ONLINE"
    assert bad_cam not in coordinator.cached_status
