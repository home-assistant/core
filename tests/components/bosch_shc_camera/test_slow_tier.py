"""Tests for slow_tier.py's pure per-camera helpers."""

from homeassistant.components.bosch_shc_camera.slow_tier import (
    CamContext,
    _dispatch_slow_tier_result,
    _slow_tier_endpoint_list,
    err_str,
)


def _ctx(
    hw: str = "CAMERA_OUTDOOR",
    is_gen2: bool = False,
    pan_limit: int = 0,
    has_light: bool = False,
) -> CamContext:
    return CamContext(
        hw=hw,
        is_gen2=is_gen2,
        is_online=True,
        privacy_on=False,
        do_slow_cam=True,
        pan_limit=pan_limit,
        has_light=has_light,
    )


def test_endpoint_list_is_motion_only() -> None:
    """Only `motion` is fetched — every other endpoint had no reader (bug-hunt 2026-07-27)."""
    assert _slow_tier_endpoint_list(_ctx()) == ["motion"]
    assert _slow_tier_endpoint_list(_ctx(hw="HOME_Eyes_Outdoor", is_gen2=True)) == [
        "motion"
    ]
    assert _slow_tier_endpoint_list(_ctx(pan_limit=180)) == ["motion"]
    assert _slow_tier_endpoint_list(_ctx(has_light=True)) == ["motion"]


def test_err_str_falls_back_to_repr_for_empty_message() -> None:
    """TimeoutError() has an empty str() — err_str must still return something useful."""
    assert err_str(TimeoutError()) == repr(TimeoutError())


def test_err_str_uses_str_when_present() -> None:
    """A normal exception with a message uses str(), not repr()."""
    assert err_str(ValueError("boom")) == "boom"


class _FakeCoordinator:
    """Minimal coordinator stub exposing only what the dispatch handlers touch."""

    def __init__(self) -> None:
        self.motion_set_at: dict[str, float] = {}

    def is_write_locked(self, cam_id: str, set_at: dict[str, float]) -> bool:
        return False


def test_dispatch_unknown_endpoint_is_a_noop() -> None:
    """An endpoint name with no registered handler is silently ignored."""
    coordinator = _FakeCoordinator()
    data: dict[str, dict[str, object]] = {"cam1": {}}
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, data, "not_a_real_endpoint", {"x": 1}
    )
    assert data["cam1"] == {}


def test_dispatch_motion_stores_payload() -> None:
    """A well-formed motion payload is written into data[cam_id]['motion']."""
    coordinator = _FakeCoordinator()
    data: dict[str, dict[str, object]] = {"cam1": {}}
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, data, "motion", {"enabled": True}
    )
    assert data["cam1"]["motion"] == {"enabled": True}


def test_dispatch_motion_skipped_while_write_locked() -> None:
    """A poll inside the write-lock window must not revert an optimistic write."""

    class _LockedCoordinator(_FakeCoordinator):
        def is_write_locked(self, cam_id: str, set_at: dict[str, float]) -> bool:
            return True

    coordinator = _LockedCoordinator()
    data: dict[str, dict[str, object]] = {
        "cam1": {"motion": {"enabled": True, "motionAlarmConfiguration": "HIGH"}}
    }
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, data, "motion", {"enabled": False}
    )
    assert data["cam1"]["motion"] == {
        "enabled": True,
        "motionAlarmConfiguration": "HIGH",
    }
