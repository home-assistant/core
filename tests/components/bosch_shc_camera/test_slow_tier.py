"""Tests for slow_tier.py's pure per-camera helpers."""

import pytest

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


def test_endpoint_list_gen1_base_endpoints() -> None:
    """A Gen1 camera with no pan/light gets the base + Gen1 zone endpoints."""
    endpoints = _slow_tier_endpoint_list(_ctx())
    assert "motion_sensitive_areas" in endpoints
    assert "privacy_masks" in endpoints
    assert "zones" not in endpoints
    assert "privateAreas" not in endpoints
    # Gen1-only endpoints must not leak in
    assert "ledlights" not in endpoints
    assert "audioDetectionConfig" not in endpoints


def test_endpoint_list_gen2_outdoor_uses_zones_and_private_areas() -> None:
    """Gen2 Outdoor II uses zones + privateAreas (polygons), not the Gen1 rectangles."""
    endpoints = _slow_tier_endpoint_list(_ctx(hw="HOME_Eyes_Outdoor", is_gen2=True))
    assert "zones" in endpoints
    assert "privateAreas" in endpoints
    assert "motion_sensitive_areas" not in endpoints
    assert "privacy_masks" not in endpoints
    # Gen2-only endpoints must be present
    assert "ledlights" in endpoints
    assert "audioDetectionConfig" in endpoints
    # Not Indoor II — no alarm system endpoints
    assert "alarm_settings" not in endpoints


@pytest.mark.parametrize("hw", ["HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"])
def test_endpoint_list_gen2_indoor_ii_skips_private_areas_adds_alarm(
    hw: str,
) -> None:
    """Gen2 Indoor II returns 442 on privateAreas — must be skipped; alarm endpoints added."""
    endpoints = _slow_tier_endpoint_list(_ctx(hw=hw, is_gen2=True))
    assert "zones" in endpoints
    assert "privateAreas" not in endpoints
    assert "alarm_settings" in endpoints
    assert "alarmStatus" in endpoints
    assert "iconLedBrightness" in endpoints
    assert "privacy_sound_override" in endpoints


def test_endpoint_list_pan_limit_adds_autofollow() -> None:
    """A camera reporting a pan limit gets the autofollow endpoint."""
    assert "autofollow" in _slow_tier_endpoint_list(_ctx(pan_limit=180))
    assert "autofollow" not in _slow_tier_endpoint_list(_ctx(pan_limit=0))


def test_endpoint_list_has_light_adds_lighting_options() -> None:
    """A camera with light hardware gets the lighting_options endpoint."""
    assert "lighting_options" in _slow_tier_endpoint_list(_ctx(has_light=True))
    assert "lighting_options" not in _slow_tier_endpoint_list(_ctx(has_light=False))


def test_err_str_falls_back_to_repr_for_empty_message() -> None:
    """TimeoutError() has an empty str() — err_str must still return something useful."""
    assert err_str(TimeoutError()) == repr(TimeoutError())


def test_err_str_uses_str_when_present() -> None:
    """A normal exception with a message uses str(), not repr()."""
    assert err_str(ValueError("boom")) == "boom"


class _FakeCoordinator:
    """Minimal coordinator stub exposing only what the dispatch handlers touch."""

    def __init__(self) -> None:
        self.wifiinfo_cache: dict[str, object] = {}
        self.ambient_light_cache: dict[str, object] = {}
        self.rules_cache: dict[str, object] = {}
        self.arming_cache: dict[str, object] = {}
        self.alarm_status_cache: dict[str, object] = {}
        self.motion_set_at: dict[str, float] = {}
        self.privacy_sound_set_at: dict[str, float] = {}
        self.firmware_set_at: dict[str, float] = {}
        self.lighting_options_set_at: dict[str, float] = {}
        self.ledlights_set_at: dict[str, float] = {}
        self.intrusion_config_set_at: dict[str, float] = {}
        self.audio_detection_set_at: dict[str, float] = {}
        self.alarm_settings_set_at: dict[str, float] = {}
        self.timestamp_set_at: dict[str, float] = {}
        self.arming_set_at: dict[str, float] = {}

    def is_write_locked(self, cam_id: str, set_at: dict[str, float]) -> bool:
        return False


def test_dispatch_unknown_endpoint_is_a_noop() -> None:
    """An endpoint name with no registered handler is silently ignored."""
    coordinator = _FakeCoordinator()
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, {}, lambda *a: None, "not_a_real_endpoint", {"x": 1}
    )
    # Nothing should have been touched.
    assert coordinator.wifiinfo_cache == {}


def test_dispatch_wifiinfo_stores_dict_payload() -> None:
    """A well-formed dict payload is cached as-is."""
    coordinator = _FakeCoordinator()
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, {}, lambda *a: None, "wifiinfo", {"ssid": "test"}
    )
    assert coordinator.wifiinfo_cache["cam1"] == {"ssid": "test"}


def test_dispatch_wifiinfo_ignores_malformed_non_dict_payload() -> None:
    """A malformed-but-200 (non-dict) body must not overwrite the cache (chaos-injection regression)."""
    coordinator = _FakeCoordinator()
    coordinator.wifiinfo_cache["cam1"] = {"ssid": "previously-good"}
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, {}, lambda *a: None, "wifiinfo", ["not", "a", "dict"]
    )
    assert coordinator.wifiinfo_cache["cam1"] == {"ssid": "previously-good"}


def test_dispatch_rules_defaults_to_empty_list_on_bad_shape() -> None:
    """A non-list rules payload is coerced to an empty list, never raises."""
    coordinator = _FakeCoordinator()
    _dispatch_slow_tier_result(
        coordinator, "cam1", {}, {}, lambda *a: None, "rules", {"unexpected": "shape"}
    )
    assert coordinator.rules_cache["cam1"] == []


def test_dispatch_alarm_status_fires_intrusion_event_and_updates_arming() -> None:
    """alarmStatus=ACTIVE both fires the intrusion callback and flips arming_cache."""
    coordinator = _FakeCoordinator()
    fired: list[tuple[str, str, dict[str, object]]] = []
    _dispatch_slow_tier_result(
        coordinator,
        "cam1",
        {"title": "Front Door"},
        {},
        lambda cam_id, title, data: fired.append((cam_id, title, data)),
        "alarmStatus",
        {"intrusionSystem": "ACTIVE"},
    )
    assert coordinator.arming_cache["cam1"] is True
    assert fired == [("cam1", "Front Door", {"intrusionSystem": "ACTIVE"})]
