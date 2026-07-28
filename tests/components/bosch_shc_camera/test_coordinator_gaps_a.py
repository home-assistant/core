"""Regression tests closing coordinator.py patch-coverage gaps (lower half).

Targets the missing line ranges assigned to this bucket (roughly lines
657-1524): small pure-logic helpers (get_model_config/err_str/
_alert_services/is_write_locked/is_camera_online/_in_local_write_grace/
is_lan_reachable/async_local_tcp_ping/async_outage_ping_all/
get_cam_lan_ip/should_check_status), the Repairs/notification helpers
(_refresh_notifications_disabled_issues/_refresh_firmware_update_issues/
_async_maybe_announce_camera_status/_async_handle_session_quota_hit/
_async_maybe_announce_cloud_state/_async_dispatch_cloud_alert/
_compute_status_for), and the main `_async_update_data` tick body
(the per-camera RCP-over-cloud-proxy slow-tier block + the top-level
except UpdateFailed/TimeoutError/aiohttp.ClientError dispatch).

Follows this file's own established pattern (see test_coordinator.py):
pure/near-pure methods are exercised via `SimpleNamespace` stubs bound to
the real unbound method (`BoschCameraCoordinator.<method>.__get__(coord)`)
rather than a full fake coordinator object; anything that needs real HA
plumbing (issue registry, a real config entry) uses a real
`BoschCameraCoordinator` constructed via `MockConfigEntry`.
"""

from contextlib import ExitStack
import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.slow_tier import CamContext
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={},
    )


async def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = _mock_config_entry()
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


def test_get_model_config_reads_cached_hw_version() -> None:
    """get_model_config() looks up the cached hw_version and delegates to models.py."""
    coord = SimpleNamespace(hw_version={CAM_ID: "HOME_Eyes_Outdoor"})
    coord.get_model_config = BoschCameraCoordinator.get_model_config.__get__(coord)

    config = coord.get_model_config(CAM_ID)

    assert config.generation >= 2


def test_get_model_config_defaults_when_hw_version_unknown() -> None:
    """No cached hw_version at all falls back to the generic 'CAMERA' model."""
    coord = SimpleNamespace(hw_version={})
    coord.get_model_config = BoschCameraCoordinator.get_model_config.__get__(coord)

    config = coord.get_model_config(CAM_ID)

    assert config is not None


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        pytest.param(ValueError("boom"), "boom", id="non_empty_message"),
        pytest.param(
            TimeoutError(), repr(TimeoutError()), id="empty_message_falls_back_to_repr"
        ),
    ],
)
def test_err_str(err: BaseException, expected: str) -> None:
    """err_str() falls back to repr() for exceptions with no message."""
    assert BoschCameraCoordinator.err_str(err) == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, [], id="unset_returns_empty"),
        pytest.param({"alert_notify_service": ""}, [], id="empty_string_returns_empty"),
        pytest.param(
            {"alert_notify_service": "notify.mobile_app"},
            ["notify.mobile_app"],
            id="bare_string_wrapped_in_list",
        ),
        pytest.param(
            {"alert_notify_service": ["notify.a", "notify.b"]},
            ["notify.a", "notify.b"],
            id="list_passed_through",
        ),
    ],
)
def test_alert_services(options: dict[str, Any], expected: list[str]) -> None:
    """_alert_services() normalizes the option into a list of service names."""
    coord = SimpleNamespace(options=options)
    coord._alert_services = BoschCameraCoordinator._alert_services.__get__(coord)

    assert coord._alert_services() == expected


@pytest.mark.parametrize(
    ("set_at", "now", "expected"),
    [
        pytest.param({}, 100.0, False, id="never_written_not_locked"),
        pytest.param({CAM_ID: 90.0}, 100.0, True, id="recent_write_still_locked"),
        pytest.param({CAM_ID: 50.0}, 100.0, False, id="old_write_no_longer_locked"),
    ],
)
def test_is_write_locked(set_at: dict[str, float], now: float, expected: bool) -> None:
    """is_write_locked() honors the WRITE_LOCK_SECS eventual-consistency window."""
    coord = SimpleNamespace(WRITE_LOCK_SECS=30.0)
    coord.is_write_locked = BoschCameraCoordinator.is_write_locked.__get__(coord)

    with patch("time.monotonic", return_value=now):
        assert coord.is_write_locked(CAM_ID, set_at) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({CAM_ID: {"status": "ONLINE"}}, True, id="online"),
        pytest.param({CAM_ID: {"status": "OFFLINE"}}, False, id="offline"),
        pytest.param({}, False, id="camera_missing_from_data"),
    ],
)
def test_is_camera_online(data: dict[str, Any], expected: bool) -> None:
    """is_camera_online() reads the cached status, defaulting to UNKNOWN."""
    coord = SimpleNamespace(data=data)
    coord.is_camera_online = BoschCameraCoordinator.is_camera_online.__get__(coord)

    assert coord.is_camera_online(CAM_ID) == expected


@pytest.mark.parametrize(
    ("local_write_at", "now", "expected"),
    [
        pytest.param({}, 100.0, False, id="never_written"),
        pytest.param({CAM_ID: 90.0}, 100.0, True, id="within_grace"),
        pytest.param({CAM_ID: 50.0}, 100.0, False, id="outside_grace"),
    ],
)
def test_in_local_write_grace(
    local_write_at: dict[str, float], now: float, expected: bool
) -> None:
    """_in_local_write_grace() honors LOCAL_WRITE_GRACE_S."""
    coord = SimpleNamespace(
        local_write_at=local_write_at,
        LOCAL_WRITE_GRACE_S=BoschCameraCoordinator.LOCAL_WRITE_GRACE_S,
    )
    coord._in_local_write_grace = BoschCameraCoordinator._in_local_write_grace.__get__(
        coord
    )

    assert coord._in_local_write_grace(CAM_ID, now=now) == expected


@pytest.mark.parametrize(
    ("lan_tcp_reachable", "in_grace", "expected"),
    [
        pytest.param({}, False, None, id="no_entry_no_grace_unknown"),
        pytest.param({}, True, True, id="no_entry_in_grace_assumed_reachable"),
        pytest.param({CAM_ID: (True, 0.0)}, False, True, id="entry_reachable"),
        pytest.param(
            {CAM_ID: (False, 0.0)}, True, True, id="entry_unreachable_but_in_grace"
        ),
        pytest.param(
            {CAM_ID: (False, 0.0)}, False, False, id="entry_unreachable_no_grace"
        ),
    ],
)
def test_is_lan_reachable(
    lan_tcp_reachable: dict[str, tuple[bool, float]],
    in_grace: bool,
    expected: bool | None,
) -> None:
    """is_lan_reachable() honors the post-local-write grace window."""
    coord = SimpleNamespace(
        lan_tcp_reachable=lan_tcp_reachable,
        _in_local_write_grace=lambda _cam_id: in_grace,
    )
    coord.is_lan_reachable = BoschCameraCoordinator.is_lan_reachable.__get__(coord)

    assert coord.is_lan_reachable(CAM_ID) is expected


async def test_async_local_tcp_ping_no_known_lan_ip_returns_false() -> None:
    """No known LAN IP at all short-circuits before opening any connection."""
    coord = SimpleNamespace(get_cam_lan_ip=lambda _cam_id: None)
    coord.async_local_tcp_ping = BoschCameraCoordinator.async_local_tcp_ping.__get__(
        coord
    )

    with patch("asyncio.open_connection") as mock_open_connection:
        result = await coord.async_local_tcp_ping(CAM_ID)

    assert result is False
    mock_open_connection.assert_not_called()


@pytest.mark.parametrize(
    "raised",
    [
        pytest.param(TimeoutError(), id="timeout_error"),
        pytest.param(OSError("connection refused"), id="os_error"),
    ],
)
async def test_async_local_tcp_ping_connection_failure_returns_false(
    raised: BaseException,
) -> None:
    """A connect timeout or OSError is caught and recorded as unreachable."""
    coord = SimpleNamespace(
        get_cam_lan_ip=lambda _cam_id: "192.168.1.50",
        lan_tcp_reachable={},
    )
    coord.async_local_tcp_ping = BoschCameraCoordinator.async_local_tcp_ping.__get__(
        coord
    )

    with patch("asyncio.open_connection", side_effect=raised):
        result = await coord.async_local_tcp_ping(CAM_ID)

    assert result is False
    assert coord.lan_tcp_reachable[CAM_ID][0] is False


async def test_async_outage_ping_all_throttled_skips_within_30s() -> None:
    """A second call within 30s of the last outage ping is a no-op."""
    coord = SimpleNamespace(
        _last_outage_ping_at=95.0,
        data={},
        rcp_lan_ip_cache={},
        async_local_tcp_ping=AsyncMock(),
        async_update_listeners=MagicMock(),
    )
    coord.async_outage_ping_all = BoschCameraCoordinator.async_outage_ping_all.__get__(
        coord
    )

    with patch("time.monotonic", return_value=100.0):
        await coord.async_outage_ping_all()

    coord.async_local_tcp_ping.assert_not_called()
    coord.async_update_listeners.assert_not_called()


async def test_async_outage_ping_all_no_known_cameras_returns_early() -> None:
    """No cameras in `data` nor `rcp_lan_ip_cache` means nothing to ping."""
    coord = SimpleNamespace(
        _last_outage_ping_at=0.0,
        data={},
        rcp_lan_ip_cache={},
        async_local_tcp_ping=AsyncMock(),
        async_update_listeners=MagicMock(),
    )
    coord.async_outage_ping_all = BoschCameraCoordinator.async_outage_ping_all.__get__(
        coord
    )

    with patch("time.monotonic", return_value=1000.0):
        await coord.async_outage_ping_all()

    coord.async_local_tcp_ping.assert_not_called()
    coord.async_update_listeners.assert_not_called()


async def test_async_outage_ping_all_pings_known_cameras_and_notifies() -> None:
    """Cameras from both `data` and `rcp_lan_ip_cache` are pinged, then listeners notified."""
    coord = SimpleNamespace(
        _last_outage_ping_at=0.0,
        data={CAM_ID: {}},
        rcp_lan_ip_cache={"OTHER-CAM": "192.168.1.60"},
        async_local_tcp_ping=AsyncMock(side_effect=[True, False]),
        async_update_listeners=MagicMock(),
    )
    coord.async_outage_ping_all = BoschCameraCoordinator.async_outage_ping_all.__get__(
        coord
    )

    with patch("time.monotonic", return_value=1000.0):
        await coord.async_outage_ping_all()

    assert coord.async_local_tcp_ping.await_count == 2
    coord.async_update_listeners.assert_called_once()


def test_get_cam_lan_ip_falls_back_to_local_creds_cache() -> None:
    """No RCP-discovered LAN IP falls back to the cached LOCAL Digest host."""
    coord = SimpleNamespace(
        rcp_lan_ip_cache={},
        local_creds_cache={CAM_ID: {"host": "192.168.1.77", "port": 443}},
    )
    coord.get_cam_lan_ip = BoschCameraCoordinator.get_cam_lan_ip.__get__(coord)

    assert coord.get_cam_lan_ip(CAM_ID) == "192.168.1.77"


def test_get_cam_lan_ip_returns_none_when_nothing_cached() -> None:
    """Neither cache having an entry returns None (not yet discovered)."""
    coord = SimpleNamespace(rcp_lan_ip_cache={}, local_creds_cache={})
    coord.get_cam_lan_ip = BoschCameraCoordinator.get_cam_lan_ip.__get__(coord)

    assert coord.get_cam_lan_ip(CAM_ID) is None


@pytest.mark.parametrize(
    ("offline_since", "per_cam_last", "now", "expected"),
    [
        pytest.param({}, -math.inf, 100.0, True, id="never_checked_always_due"),
        pytest.param({}, 95.0, 100.0, False, id="normal_interval_not_yet_due"),
        pytest.param(
            # offline_since must be non-zero: `if offline_since and ...` is a
            # truthiness check, so 0.0 would be wrongly treated as "not offline".
            {CAM_ID: 100.0},
            1000.0,
            2000.0,
            True,
            id="persistently_offline_extended_interval_due",
        ),
        pytest.param(
            {CAM_ID: 100.0},
            1900.0,
            2000.0,
            False,
            id="persistently_offline_extended_interval_not_due",
        ),
    ],
)
def test_should_check_status(
    offline_since: dict[str, float],
    per_cam_last: float,
    now: float,
    expected: bool,
) -> None:
    """should_check_status() extends the interval for persistently-offline cameras."""
    coord = SimpleNamespace(
        per_cam_status_at={CAM_ID: per_cam_last},
        offline_since=offline_since,
        _OFFLINE_EXTENDED_INTERVAL=900,
    )
    coord.should_check_status = BoschCameraCoordinator.should_check_status.__get__(
        coord
    )

    assert coord.should_check_status(CAM_ID, now, interval_status=60) == expected


async def test_refresh_notifications_disabled_issues_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A camera with movement/person notifications disabled gets a Repairs issue."""
    coord = await _make_coordinator(hass)
    coord.notifications_cache = {CAM_ID: {"movement": False, "person": True}}
    coord.data = {CAM_ID: {"info": {"title": "Front Door"}}}

    coord._refresh_notifications_disabled_issues()

    issue = issue_registry.async_get_issue(DOMAIN, f"notifications_disabled_{CAM_ID}")
    assert issue is not None
    assert CAM_ID in coord._notif_disabled_logged


async def test_refresh_notifications_disabled_issues_log_message_matches_camera_only_scope(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The one-time WARNING log describes this build's real behavior.

    Regression for Copilot review round 15: the old wording told users to
    enable a "notification switch(es) in Home Assistant" and warned that
    "binary sensor(s)" would stay Clear — but this camera-only Core PR ships
    no switch or binary_sensor platform at all, so both entities described
    don't exist. The message (and the matching `notifications_disabled`
    Repairs-issue translation string) must instead describe the real
    consequence: the `bosch_shc_camera_motion`/`_person` bus events never
    firing, and the real fix location (the Bosch Smart Home app only).
    """
    coord = await _make_coordinator(hass)
    coord.notifications_cache = {CAM_ID: {"movement": False, "person": True}}
    coord.data = {CAM_ID: {"info": {"title": "Front Door"}}}

    coord._refresh_notifications_disabled_issues()

    assert "bosch_shc_camera_" in caplog.text
    assert "Bosch Smart Home app" in caplog.text
    assert "switch" not in caplog.text.lower()
    assert "binary sensor" not in caplog.text.lower()


async def test_refresh_notifications_disabled_issues_clears_when_reenabled(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Re-enabling notifications deletes the issue and clears the logged-set entry."""
    coord = await _make_coordinator(hass)
    coord.notifications_cache = {CAM_ID: {"movement": True, "person": True}}
    coord.data = {CAM_ID: {"info": {"title": "Front Door"}}}
    coord._notif_disabled_logged.add(CAM_ID)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"notifications_disabled_{CAM_ID}",
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="notifications_disabled",
        translation_placeholders={"camera": "Front Door", "types": "Movement"},
    )

    coord._refresh_notifications_disabled_issues()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"notifications_disabled_{CAM_ID}")
        is None
    )
    assert CAM_ID not in coord._notif_disabled_logged


def test_refresh_notifications_disabled_issues_skips_camera_with_no_data() -> None:
    """A camera with an empty notifications cache entry is skipped entirely."""
    coord = SimpleNamespace(
        notifications_cache={CAM_ID: {}},
        data={},
        _notif_disabled_logged=set(),
    )
    coord._refresh_notifications_disabled_issues = (
        BoschCameraCoordinator._refresh_notifications_disabled_issues.__get__(coord)
    )

    coord._refresh_notifications_disabled_issues()  # must not raise

    assert coord._notif_disabled_logged == set()


def test_refresh_firmware_update_issues_logs_once_when_outdated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A camera not up to date logs an INFO once, not on every tick."""
    coord = SimpleNamespace(
        firmware_cache={
            CAM_ID: {
                "upToDate": False,  # codespell:ignore
                "current": "9.40.102",
                "update": "9.40.104",
            }
        },
        data={CAM_ID: {"info": {"title": "Front Door"}}},
        _fw_update_alerted=set(),
    )
    coord._refresh_firmware_update_issues = (
        BoschCameraCoordinator._refresh_firmware_update_issues.__get__(coord)
    )

    with caplog.at_level("INFO"):
        coord._refresh_firmware_update_issues()
        coord._refresh_firmware_update_issues()

    assert CAM_ID in coord._fw_update_alerted
    assert caplog.text.count("Firmware update available") == 1


def test_refresh_firmware_update_issues_clears_when_up_to_date() -> None:
    """Once up to date, the alerted-set entry is discarded so a future update re-alerts."""
    coord = SimpleNamespace(
        firmware_cache={CAM_ID: {"upToDate": True}},  # codespell:ignore
        data={},
        _fw_update_alerted={CAM_ID},
    )
    coord._refresh_firmware_update_issues = (
        BoschCameraCoordinator._refresh_firmware_update_issues.__get__(coord)
    )

    coord._refresh_firmware_update_issues()

    assert CAM_ID not in coord._fw_update_alerted


@pytest.mark.parametrize(
    "fw_cache",
    [
        pytest.param({CAM_ID: {}}, id="empty_entry_skipped"),
        pytest.param({CAM_ID: {"current": "1.0"}}, id="no_up_to_date_key_skipped"),
    ],
)
def test_refresh_firmware_update_issues_skips_incomplete_data(
    fw_cache: dict[str, Any],
) -> None:
    """No fetched firmware data yet must not produce a false-positive transition."""
    coord = SimpleNamespace(firmware_cache=fw_cache, data={}, _fw_update_alerted=set())
    coord._refresh_firmware_update_issues = (
        BoschCameraCoordinator._refresh_firmware_update_issues.__get__(coord)
    )

    coord._refresh_firmware_update_issues()  # must not raise

    assert coord._fw_update_alerted == set()


def _announce_coord(**overrides: Any) -> SimpleNamespace:
    base = SimpleNamespace(
        _last_camera_status={},
        _offline_seen_at={},
        data={CAM_ID: {"info": {"title": "Front Door"}}},
        _alert_services=list,
        hass=MagicMock(services=MagicMock(async_call=AsyncMock())),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    base._async_maybe_announce_camera_status = (
        BoschCameraCoordinator._async_maybe_announce_camera_status.__get__(base)
    )
    return base


async def test_announce_camera_status_first_observation_is_silent() -> None:
    """The first-ever observation for a camera just records the baseline."""
    coord = _announce_coord()

    await coord._async_maybe_announce_camera_status(CAM_ID, "online")

    assert coord._last_camera_status[CAM_ID] == "online"
    coord.hass.services.async_call.assert_not_called()


async def test_announce_camera_status_noop_when_unchanged() -> None:
    """Same status as last tick is a no-op, no notification attempted."""
    coord = _announce_coord(_last_camera_status={CAM_ID: "online"})

    await coord._async_maybe_announce_camera_status(CAM_ID, "online")

    coord.hass.services.async_call.assert_not_called()


@pytest.mark.parametrize(
    ("last", "new"),
    [
        pytest.param("unknown", "online", id="from_unknown_is_silent"),
        pytest.param("online", "unknown", id="to_unknown_is_silent"),
    ],
)
async def test_announce_camera_status_skips_unknown_transitions(
    last: str, new: str
) -> None:
    """Transitions involving 'unknown' never notify — coordinator hiccup, not a real flip."""
    coord = _announce_coord(_last_camera_status={CAM_ID: last})

    await coord._async_maybe_announce_camera_status(CAM_ID, new)

    assert coord._last_camera_status[CAM_ID] == new
    coord.hass.services.async_call.assert_not_called()


async def test_announce_camera_status_offline_grace_window_delays_notify() -> None:
    """A fresh offline observation starts the grace timer without notifying yet."""
    coord = _announce_coord(_last_camera_status={CAM_ID: "online"})

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_camera_status(CAM_ID, "offline")

    assert CAM_ID in coord._offline_seen_at
    coord.hass.services.async_call.assert_not_called()
    # The baseline is held at "online" until the grace elapses.
    assert coord._last_camera_status[CAM_ID] == "online"


async def test_announce_camera_status_lazy_inits_offline_seen_at_when_missing() -> None:
    """A SimpleNamespace stub with no `_offline_seen_at` attribute at all is lazily inited.

    Covers the defensive `hasattr` guard added for test stubs that bypass
    `__init__` entirely.
    """
    coord = SimpleNamespace(
        _last_camera_status={CAM_ID: "online"},
        data={CAM_ID: {"info": {"title": "Front Door"}}},
        _alert_services=list,
        hass=MagicMock(services=MagicMock(async_call=AsyncMock())),
    )
    coord._async_maybe_announce_camera_status = (
        BoschCameraCoordinator._async_maybe_announce_camera_status.__get__(coord)
    )
    assert not hasattr(coord, "_offline_seen_at")

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_camera_status(CAM_ID, "offline")

    assert coord._offline_seen_at == {CAM_ID: 1000.0}


async def test_announce_camera_status_offline_still_within_grace_on_later_tick() -> (
    None
):
    """A second offline tick still inside the grace window keeps waiting silently."""
    coord = _announce_coord(
        _last_camera_status={CAM_ID: "online"},
        _offline_seen_at={CAM_ID: 1000.0},
    )

    with patch("time.monotonic", return_value=1010.0):
        await coord._async_maybe_announce_camera_status(CAM_ID, "offline")

    coord.hass.services.async_call.assert_not_called()
    assert coord._last_camera_status[CAM_ID] == "online"
    # The original observation timestamp is untouched — only a *fresh*
    # offline observation (seen is None) records a new one.
    assert coord._offline_seen_at[CAM_ID] == 1000.0


async def test_announce_camera_status_no_notify_service_configured_is_debug_only() -> (
    None
):
    """No `alert_notify_service` configured skips the notify call cleanly."""
    coord = _announce_coord(
        _last_camera_status={CAM_ID: "online"},
        _offline_seen_at={CAM_ID: 0.0},
    )

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_camera_status(CAM_ID, "offline")

    coord.hass.services.async_call.assert_not_called()


@pytest.mark.parametrize(
    ("last", "new"),
    [
        pytest.param("online", "offline", id="offline_message"),
        pytest.param("offline", "online", id="recovery_message"),
    ],
)
async def test_announce_camera_status_sends_notification_via_configured_service(
    last: str, new: str
) -> None:
    """A real online<->offline transition with a configured service sends a notify call."""
    coord = _announce_coord(
        _last_camera_status={CAM_ID: last},
        _offline_seen_at={CAM_ID: 0.0},
        _alert_services=lambda: ["notify.mobile_app"],
    )

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_camera_status(CAM_ID, new)

    coord.hass.services.async_call.assert_called_once()
    assert coord._last_camera_status[CAM_ID] == new


async def test_announce_camera_status_notify_failure_is_swallowed() -> None:
    """A raising notify-service call must not propagate out of the announce helper."""
    coord = _announce_coord(
        _last_camera_status={CAM_ID: "online"},
        _offline_seen_at={CAM_ID: 0.0},
        _alert_services=lambda: ["notify.broken"],
    )
    coord.hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("boom"))

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_camera_status(
            CAM_ID, "offline"
        )  # must not raise


def _quota_coord() -> SimpleNamespace:
    coord = SimpleNamespace(
        _session_quota_hits={},
        _SESSION_QUOTA_WINDOW_S=300.0,
        _SESSION_QUOTA_NOTIFY_THRESHOLD=3,
        data={CAM_ID: {"info": {"title": "Front Door"}}},
        hass=MagicMock(services=MagicMock(async_call=AsyncMock())),
    )
    coord._async_handle_session_quota_hit = (
        BoschCameraCoordinator._async_handle_session_quota_hit.__get__(coord)
    )
    return coord


async def test_session_quota_hit_below_threshold_does_not_notify() -> None:
    """Fewer than the threshold of hits in the window must not fire a notification."""
    coord = _quota_coord()

    await coord._async_handle_session_quota_hit(CAM_ID)
    await coord._async_handle_session_quota_hit(CAM_ID)

    coord.hass.services.async_call.assert_not_called()


async def test_session_quota_hit_at_threshold_notifies() -> None:
    """Reaching the notify threshold within the window fires a persistent_notification."""
    coord = _quota_coord()

    for _ in range(3):
        await coord._async_handle_session_quota_hit(CAM_ID)

    coord.hass.services.async_call.assert_called_once()
    call = coord.hass.services.async_call.call_args
    assert call.args[0] == "persistent_notification"


async def test_session_quota_hit_prunes_stale_entries_outside_window() -> None:
    """Hits older than the window are pruned before the new one is counted."""
    coord = _quota_coord()
    coord._session_quota_hits[CAM_ID] = [
        0.0,
        1.0,
    ]  # will be outside the window at t=1000

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_handle_session_quota_hit(CAM_ID)

    assert coord._session_quota_hits[CAM_ID] == [1000.0]


async def test_session_quota_hit_notification_failure_is_swallowed() -> None:
    """A raising persistent_notification call must not propagate (non-fatal per docstring)."""
    coord = _quota_coord()
    coord.hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("boom"))

    for _ in range(3):
        await coord._async_handle_session_quota_hit(CAM_ID)  # must not raise


def _cloud_state_coord(**overrides: Any) -> SimpleNamespace:
    base = SimpleNamespace(
        cloud_outage_notified=False,
        _cloud_outage_started_at=None,
        _CLOUD_OUTAGE_NOTIFY_AFTER_S=60.0,
        _async_dispatch_cloud_alert=AsyncMock(),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    base._async_maybe_announce_cloud_state = (
        BoschCameraCoordinator._async_maybe_announce_cloud_state.__get__(base)
    )
    return base


async def test_cloud_state_success_with_no_prior_outage_resets_tracker() -> None:
    """A success tick while healthy just resets the outage-start tracker."""
    coord = _cloud_state_coord(_cloud_outage_started_at=50.0)

    await coord._async_maybe_announce_cloud_state(success=True)

    assert coord._cloud_outage_started_at is None
    coord._async_dispatch_cloud_alert.assert_not_called()


async def test_cloud_state_success_after_announced_outage_announces_recovery() -> None:
    """A success tick after an announced outage fires the recovery alert."""
    coord = _cloud_state_coord(
        cloud_outage_notified=True,
        _persist_cloud_outage_flag=MagicMock(),
    )

    await coord._async_maybe_announce_cloud_state(success=True)

    assert coord.cloud_outage_notified is False
    coord._async_dispatch_cloud_alert.assert_awaited_once_with(recovered=True)


async def test_cloud_state_failure_starts_timer_without_announcing() -> None:
    """The first failure tick just starts the outage timer."""
    coord = _cloud_state_coord()

    with patch("time.monotonic", return_value=1000.0):
        await coord._async_maybe_announce_cloud_state(success=False)

    assert coord._cloud_outage_started_at == 1000.0
    coord._async_dispatch_cloud_alert.assert_not_called()


async def test_cloud_state_failure_within_grace_does_not_announce() -> None:
    """A failure still inside the notify-after grace window stays silent."""
    coord = _cloud_state_coord(_cloud_outage_started_at=1000.0)

    with patch("time.monotonic", return_value=1010.0):
        await coord._async_maybe_announce_cloud_state(success=False)

    coord._async_dispatch_cloud_alert.assert_not_called()
    assert coord.cloud_outage_notified is False


async def test_cloud_state_failure_past_grace_announces_outage() -> None:
    """A failure that persists past the grace window fires the outage alert."""
    coord = _cloud_state_coord(
        _cloud_outage_started_at=1000.0,
        _persist_cloud_outage_flag=MagicMock(),
    )

    with patch("time.monotonic", return_value=1100.0):
        await coord._async_maybe_announce_cloud_state(success=False)

    assert coord.cloud_outage_notified is True
    coord._async_dispatch_cloud_alert.assert_awaited_once_with(recovered=False)


async def test_cloud_state_failure_already_notified_does_not_reannounce() -> None:
    """Once already notified, further failure ticks must not re-announce."""
    coord = _cloud_state_coord(
        cloud_outage_notified=True, _cloud_outage_started_at=1000.0
    )

    with patch("time.monotonic", return_value=2000.0):
        await coord._async_maybe_announce_cloud_state(success=False)

    coord._async_dispatch_cloud_alert.assert_not_called()


def _dispatch_alert_coord(**overrides: Any) -> SimpleNamespace:
    base = SimpleNamespace(
        _alert_services=list,
        hass=MagicMock(services=MagicMock(async_call=AsyncMock())),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    base._async_dispatch_cloud_alert = (
        BoschCameraCoordinator._async_dispatch_cloud_alert.__get__(base)
    )
    return base


async def test_dispatch_cloud_alert_no_service_configured_skips() -> None:
    """No configured notify service is a debug-only no-op."""
    coord = _dispatch_alert_coord()

    await coord._async_dispatch_cloud_alert(recovered=False)

    coord.hass.services.async_call.assert_not_called()


@pytest.mark.parametrize("recovered", [True, False])
async def test_dispatch_cloud_alert_sends_via_configured_service(
    recovered: bool,
) -> None:
    """Both the outage and recovery message variants call the configured service."""
    coord = _dispatch_alert_coord(_alert_services=lambda: ["notify.mobile_app"])

    await coord._async_dispatch_cloud_alert(recovered=recovered)

    coord.hass.services.async_call.assert_called_once()


async def test_dispatch_cloud_alert_notify_failure_is_swallowed() -> None:
    """A raising notify call must not propagate out of the dispatch helper."""
    coord = _dispatch_alert_coord(_alert_services=lambda: ["notify.broken"])
    coord.hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("boom"))

    await coord._async_dispatch_cloud_alert(recovered=True)  # must not raise


@pytest.mark.parametrize(
    ("cam_data", "expected"),
    [
        pytest.param({"status": "ONLINE", "events": []}, "online", id="plain_online"),
        pytest.param(
            {
                "status": "ONLINE",
                "events": [{"eventType": "TROUBLE_DISCONNECT"}],
            },
            "offline",
            id="online_but_latest_event_is_trouble_disconnect",
        ),
        pytest.param(
            {"status": "OFFLINE", "events": []}, "offline", id="plain_offline"
        ),
        pytest.param({}, "unknown", id="missing_status_defaults_unknown"),
    ],
)
def test_compute_status_for_explicit_cam_data(
    cam_data: dict[str, Any], expected: str
) -> None:
    """_compute_status_for() mirrors the status sensor's TROUBLE_DISCONNECT override."""
    coord = SimpleNamespace(data={})
    coord._compute_status_for = BoschCameraCoordinator._compute_status_for.__get__(
        coord
    )

    assert coord._compute_status_for(CAM_ID, cam_data) == expected


def test_compute_status_for_reads_from_self_data_when_no_cam_data_given() -> None:
    """Omitting `cam_data` falls back to reading `self.data`."""
    coord = SimpleNamespace(data={CAM_ID: {"status": "ONLINE", "events": []}})
    coord._compute_status_for = BoschCameraCoordinator._compute_status_for.__get__(
        coord
    )

    assert coord._compute_status_for(CAM_ID) == "online"


def test_compute_status_for_no_data_at_all_defaults_unknown() -> None:
    """A coordinator with `data=None` (pre-first-tick) must not raise."""
    coord = SimpleNamespace(data=None)
    coord._compute_status_for = BoschCameraCoordinator._compute_status_for.__get__(
        coord
    )

    assert coord._compute_status_for(CAM_ID) == "unknown"


def _cam_by_id() -> dict[str, dict[str, Any]]:
    return {
        CAM_ID: {
            "id": CAM_ID,
            "hardwareVersion": "HOME_Eyes_Outdoor",
            "title": "Front Door",
        }
    }


def _tick_data() -> dict[str, Any]:
    cam = _cam_by_id()[CAM_ID]
    return {CAM_ID: {"info": cam, "status": "ONLINE", "events": []}}


def _patch_tick_collaborators(
    *,
    ctx: CamContext,
    session: MagicMock,
    rcp_update_mock: AsyncMock,
) -> list[Any]:
    """Return the standard set of (unentered) patches for a full tick.

    Every collaborator `_async_update_data` delegates to is stubbed except
    the per-camera RCP-over-cloud-proxy slow-tier block itself, which is
    the code under test. `rcp_update_mock` is passed in (rather than
    created here) so callers can assert on it after the patches are
    unwound — the mock *instance* keeps its call history even after
    `patch.object` restores the original class attribute.
    """
    cam_by_id = _cam_by_id()
    data = _tick_data()

    return [
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.fetch_camera_list",
            new=AsyncMock(return_value=([cam_by_id[CAM_ID]], "tok", {})),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.ensure_feature_flags",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.ensure_protocol_checked",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.poll_statuses",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.poll_events",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.build_data_and_dispatch",
            new=AsyncMock(return_value=data),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator._poll_cam_info_caches",
            new=MagicMock(),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator._compute_cam_context",
            new=MagicMock(return_value=ctx),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator._poll_cam_control",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator._poll_slow_tier_endpoints",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.run_housekeeping",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            BoschCameraCoordinator, "_async_update_rcp_data", new=rcp_update_mock
        ),
    ]


def _rcp_resp_cm(status: int, body: dict[str, Any] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body or {})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


async def _run_tick_with_patches(
    coord: BoschCameraCoordinator, patches: list[Any]
) -> dict[str, Any]:
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return await coord._async_update_data()


def _make_ctx(*, is_online: bool, privacy_on: bool) -> CamContext:
    return CamContext(
        hw="HOME_Eyes_Outdoor",
        is_gen2=True,
        is_online=is_online,
        privacy_on=privacy_on,
        do_slow_cam=True,
        pan_limit=0,
        has_light=False,
    )


async def test_async_update_data_full_tick_online_privacy_off_updates_rcp(
    hass: HomeAssistant,
) -> None:
    """A healthy online tick with privacy off opens the RCP proxy connection.

    Covers the FCM-healthy `event_interval` branch (fcm_healthy=True) and
    the full per-camera RCP-over-cloud-proxy slow-tier block on a
    successful (200) proxy connection with a valid `urls[0]` entry.
    """
    coord = await _make_coordinator(hass)
    coord.fcm_healthy = True
    ctx = _make_ctx(is_online=True, privacy_on=False)
    session = MagicMock()
    session.put = MagicMock(
        return_value=_rcp_resp_cm(
            200, {"urls": ["proxy-01.live.cbs.boschsecurity.com:42090/abcHash"]}
        )
    )
    rcp_update_mock = AsyncMock()

    data = await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    assert data == _tick_data()
    rcp_update_mock.assert_awaited_once_with(
        CAM_ID, "proxy-01.live.cbs.boschsecurity.com:42090", "abcHash"
    )


async def test_async_update_data_second_tick_advances_events_and_slow_timestamps(
    hass: HomeAssistant,
) -> None:
    """On a non-first tick, a successful fetch advances `_last_events`/`_last_slow`.

    The very first tick always forces `do_events`/`do_slow` False (fast
    startup) — these timestamp updates only ever execute from the second
    tick onward.
    """
    coord = await _make_coordinator(hass)
    coord._first_tick_done = True
    ctx = _make_ctx(is_online=True, privacy_on=True)  # privacy on: skip RCP block
    session = MagicMock()
    rcp_update_mock = AsyncMock()

    with patch("time.monotonic", return_value=12345.0):
        await _run_tick_with_patches(
            coord,
            _patch_tick_collaborators(
                ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
            ),
        )

    assert coord._last_events == 12345.0
    assert coord._last_slow == 12345.0


async def test_async_update_data_full_tick_privacy_on_skips_rcp_fetch(
    hass: HomeAssistant,
) -> None:
    """Privacy ON for an online camera skips the RCP proxy block entirely."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=True)
    session = MagicMock()
    rcp_update_mock = AsyncMock()

    await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    session.put.assert_not_called()
    rcp_update_mock.assert_not_called()


async def test_async_update_data_full_tick_non_200_proxy_connection_is_swallowed(
    hass: HomeAssistant,
) -> None:
    """A non-(200,201) proxy connection response is logged, not raised."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=False)
    session = MagicMock()
    session.put = MagicMock(return_value=_rcp_resp_cm(503))
    rcp_update_mock = AsyncMock()

    data = await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    assert data == _tick_data()
    rcp_update_mock.assert_not_called()


@pytest.mark.parametrize(
    "raised",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientError("boom"), id="client_error"),
    ],
)
async def test_async_update_data_full_tick_proxy_connect_error_is_swallowed(
    hass: HomeAssistant, raised: BaseException
) -> None:
    """A TimeoutError/ClientError opening the proxy connection is caught per-camera.

    Must not abort the whole tick for the rest of the cameras.
    """
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=False)
    session = MagicMock()
    session.put = MagicMock(side_effect=raised)
    rcp_update_mock = AsyncMock()

    data = await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    assert data == _tick_data()
    rcp_update_mock.assert_not_called()


async def test_async_update_data_full_tick_rcp_update_failure_does_not_abort_tick(
    hass: HomeAssistant,
) -> None:
    """A failure inside `_async_update_rcp_data` itself is swallowed (outer guard)."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=False)
    session = MagicMock()
    session.put = MagicMock(
        return_value=_rcp_resp_cm(
            200, {"urls": ["proxy-01.live.cbs.boschsecurity.com:42090/abcHash"]}
        )
    )
    # Exercises the outer per-camera `except Exception` guard around the
    # whole RCP block — a failure here must not abort the tick.
    rcp_update_mock = AsyncMock(side_effect=RuntimeError("boom"))

    data = await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    assert data == _tick_data()


async def test_async_update_data_full_tick_offline_camera_skips_rcp_and_control(
    hass: HomeAssistant,
) -> None:
    """An offline camera skips the slow-tier RCP block (is_online gate)."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=False, privacy_on=False)
    session = MagicMock()
    rcp_update_mock = AsyncMock()

    await _run_tick_with_patches(
        coord,
        _patch_tick_collaborators(
            ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
        ),
    )

    session.put.assert_not_called()
    rcp_update_mock.assert_not_called()


async def test_async_update_data_notifications_disabled_check_failure_is_swallowed(
    hass: HomeAssistant,
) -> None:
    """A raising `_refresh_notifications_disabled_issues` must not abort the tick."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=True)
    session = MagicMock()
    rcp_update_mock = AsyncMock()
    patches = _patch_tick_collaborators(
        ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
    )
    patches.append(
        patch.object(
            BoschCameraCoordinator,
            "_refresh_notifications_disabled_issues",
            side_effect=RuntimeError("boom"),
        )
    )

    data = await _run_tick_with_patches(coord, patches)

    assert data == _tick_data()


async def test_async_update_data_firmware_update_check_failure_is_swallowed(
    hass: HomeAssistant,
) -> None:
    """A raising `_refresh_firmware_update_issues` must not abort the tick."""
    coord = await _make_coordinator(hass)
    ctx = _make_ctx(is_online=True, privacy_on=True)
    session = MagicMock()
    rcp_update_mock = AsyncMock()
    patches = _patch_tick_collaborators(
        ctx=ctx, session=session, rcp_update_mock=rcp_update_mock
    )
    patches.append(
        patch.object(
            BoschCameraCoordinator,
            "_refresh_firmware_update_issues",
            side_effect=RuntimeError("boom"),
        )
    )

    data = await _run_tick_with_patches(coord, patches)

    assert data == _tick_data()


@pytest.mark.parametrize(
    ("raised_exc", "dispatch_name", "dispatch_return_is_exception"),
    [
        pytest.param(
            UpdateFailed("cloud down"),
            "dispatch_update_failed",
            False,
            id="update_failed_reraised_as_is",
        ),
    ],
)
async def test_async_update_data_dispatches_update_failed(
    hass: HomeAssistant,
    raised_exc: BaseException,
    dispatch_name: str,
    dispatch_return_is_exception: bool,
) -> None:
    """An UpdateFailed raised mid-tick is dispatched and re-raised unchanged."""
    coord = await _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.fetch_camera_list",
            new=AsyncMock(side_effect=raised_exc),
        ),
        patch(
            f"homeassistant.components.bosch_shc_camera.coordinator.{dispatch_name}",
            new=AsyncMock(),
        ) as mock_dispatch,
        pytest.raises(UpdateFailed),
    ):
        await coord._async_update_data()

    mock_dispatch.assert_awaited_once()


async def test_async_update_data_dispatches_timeout_error(
    hass: HomeAssistant,
) -> None:
    """A TimeoutError raised mid-tick is dispatched and re-raised as the mapped exception."""
    coord = await _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.fetch_camera_list",
            new=AsyncMock(side_effect=TimeoutError("slow")),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.dispatch_timeout",
            new=AsyncMock(return_value=UpdateFailed("mapped timeout")),
        ) as mock_dispatch,
        pytest.raises(UpdateFailed, match="mapped timeout"),
    ):
        await coord._async_update_data()

    mock_dispatch.assert_awaited_once()


async def test_async_update_data_dispatches_client_error(
    hass: HomeAssistant,
) -> None:
    """An aiohttp.ClientError raised mid-tick is dispatched and re-raised as the mapped exception."""
    coord = await _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.fetch_camera_list",
            new=AsyncMock(side_effect=aiohttp.ClientError("boom")),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.coordinator.dispatch_client_error",
            new=AsyncMock(return_value=UpdateFailed("mapped client error")),
        ) as mock_dispatch,
        pytest.raises(UpdateFailed, match="mapped client error"),
    ):
        await coord._async_update_data()

    mock_dispatch.assert_awaited_once()
