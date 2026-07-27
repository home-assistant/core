"""Tests for coordinator.py's pure helper functions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from homeassistant.components.bosch_shc_camera.camera_status import (
    _check_one_camera_status,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import (
    _is_safe_bosch_host,
    _is_safe_local_camera_host,
    _parse_safe_rcp_proxy_url,
    get_options,
)
from homeassistant.components.bosch_shc_camera.tick_housekeeping import run_housekeeping

from tests.common import MockConfigEntry


def test_get_options_ignores_legacy_polling_keys() -> None:
    """A HACS-migrated entry's stale polling keys must not override defaults.

    scan_interval/interval_status/interval_events/snapshot_interval values
    must never override the fixed DEFAULT_OPTIONS cadence — their
    options-flow fields were removed for Bronze's appropriate-polling rule,
    but the entry data can still carry them under the same key names
    (bug-hunt 2026-07-27, Copilot review round 3).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={
            "scan_interval": 5,
            "interval_status": 5,
            "interval_events": 5,
            "snapshot_interval": 5,
            "enable_snapshots": False,
        },
    )
    opts = get_options(entry)
    assert opts["scan_interval"] == 60
    assert opts["interval_status"] == 300
    assert opts["interval_events"] == 300
    assert opts["snapshot_interval"] == 1800
    # Non-polling options still merge normally.
    assert opts["enable_snapshots"] is False


def test_get_options_defaults_when_entry_has_no_options() -> None:
    """A fresh entry with no options at all gets the plain defaults."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={}, options={})
    opts = get_options(entry)
    assert opts["scan_interval"] == 60
    assert opts["enable_snapshots"] is True


async def test_housekeeping_runs_stale_cleanup_for_definitive_empty_camera_list() -> (
    None
):
    """The last camera being removed (data == {}) must still run cleanup.

    `fetch_camera_list` already raises on any fetch failure before
    housekeeping ever runs, so an empty `data` here is a genuine
    zero-camera account, not a glitch (bug-hunt 2026-07-27, Copilot review
    round 3).
    """
    coordinator = SimpleNamespace(cleanup_stale_devices=MagicMock())
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=False)
    coordinator.cleanup_stale_devices.assert_called_once_with(set())


async def test_housekeeping_skips_cleanup_on_first_tick() -> None:
    """The fast first tick must not run cleanup.

    It would race device registration in async_setup_entry.
    """
    coordinator = SimpleNamespace(cleanup_stale_devices=MagicMock())
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=True)
    coordinator.cleanup_stale_devices.assert_not_called()


async def test_housekeeping_persists_empty_credential_snapshot_on_last_camera_removed() -> (
    None
):
    """Clearing the last camera's creds must still persist the empty snapshot.

    Otherwise a deleted camera's Digest credentials remain in `.storage`
    indefinitely (bug-hunt 2026-07-27, Copilot review round 3).
    """
    store = MagicMock()
    store.async_save = MagicMock(return_value=None)
    coordinator = SimpleNamespace(
        cleanup_stale_devices=MagicMock(),
        local_creds_store=store,
        local_creds_cache={},
        local_creds_snapshot={"OLD-CAM": {"user": "u", "password": "p", "host": "h"}},
        spawn_tracked=MagicMock(),
    )
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=False)
    assert coordinator.local_creds_snapshot == {}
    coordinator.spawn_tracked.assert_called_once()


async def test_housekeeping_persists_empty_lan_ip_snapshot_on_last_camera_removed() -> (
    None
):
    """Clearing the last camera's LAN-IP cache must still persist the empty snapshot.

    `cleanup_stale_devices()` clears `rcp_lan_ip_cache` first, but the old
    truthiness guard skipped the write, so a stale camera ID/IP was reloaded
    and pinged again after a restart (bug-hunt 2026-07-27, Copilot review
    round 5 — same class of bug already fixed for local_creds in round 3).
    """
    store = MagicMock()
    store.async_save = MagicMock(return_value=None)
    coordinator = SimpleNamespace(
        cleanup_stale_devices=MagicMock(),
        lan_ips_store=store,
        rcp_lan_ip_cache={},
        lan_ips_snapshot={"OLD-CAM": "192.0.2.1"},
        spawn_tracked=MagicMock(),
    )
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=False)
    assert coordinator.lan_ips_snapshot == {}
    coordinator.spawn_tracked.assert_called_once()


def test_is_safe_bosch_host_accepts_known_domain() -> None:
    """A real Bosch RCP proxy host passes validation."""
    assert _is_safe_bosch_host("proxy-01.live.cbs.boschsecurity.com:42090") is True


def test_is_safe_bosch_host_rejects_arbitrary_host() -> None:
    """An unvalidated proxy host is an SSRF path (bug-hunt 2026-07-27, Copilot review round 5)."""
    assert _is_safe_bosch_host("169.254.169.254:80") is False
    assert _is_safe_bosch_host("internal-service.local:8080") is False


def test_parse_safe_rcp_proxy_url_rejects_unsafe_host() -> None:
    """A malformed-but-unsafe entry is rejected before use."""
    assert _parse_safe_rcp_proxy_url("evil.example.com:443/hash", "cam1") is None


def test_parse_safe_rcp_proxy_url_accepts_bosch_host() -> None:
    """A well-formed, safe entry splits cleanly into (host, hash)."""
    assert _parse_safe_rcp_proxy_url(
        "proxy-01.live.cbs.boschsecurity.com:42090/abcHash", "cam1"
    ) == ("proxy-01.live.cbs.boschsecurity.com:42090", "abcHash")


def test_parse_safe_rcp_proxy_url_rejects_malformed_entry() -> None:
    """An entry with no '/' separator (no hash component) is rejected."""
    assert _parse_safe_rcp_proxy_url("no-slash-here", "cam1") is None


def test_is_safe_local_camera_host_accepts_private_lan_address() -> None:
    """A real LOCAL camera host is a private LAN IP:port."""
    assert _is_safe_local_camera_host("192.168.1.100:443") is True


def test_is_safe_local_camera_host_rejects_public_address() -> None:
    """A public IP is not a plausible LOCAL camera address — SSRF path.

    (Copilot review round 7): a malicious/compromised PUT /connection
    response must not redirect the credential-bearing snapshot fetch (made
    with TLS verification disabled) to an arbitrary host.
    """
    assert _is_safe_local_camera_host("8.8.8.8:443") is False


def test_is_safe_local_camera_host_rejects_hostname() -> None:
    """A hostname (not a bare IP) is rejected.

    Only IP literals are valid for a LOCAL camera's own LAN address.
    """
    assert _is_safe_local_camera_host("evil.example.com:443") is False


def test_is_safe_local_camera_host_rejects_missing_port() -> None:
    """No `:port` suffix at all must be rejected, not default to any port."""
    assert _is_safe_local_camera_host("192.168.1.100") is False


def test_is_safe_local_camera_host_rejects_out_of_range_port() -> None:
    """A port outside 1-65535 is malformed, must be rejected."""
    assert _is_safe_local_camera_host("192.168.1.100:70000") is False


def test_is_safe_local_camera_host_rejects_link_local_metadata_address() -> None:
    """169.254.169.254 is the well-known cloud-metadata SSRF target.

    Excluded explicitly even though Python's `ipaddress.is_private` counts
    link-local as private.
    """
    assert _is_safe_local_camera_host("169.254.169.254:443") is False


async def test_camera_status_preserves_last_known_on_double_probe_failure() -> None:
    """Both status probes failing must not reset a cached OFFLINE to UNKNOWN.

    Resetting to UNKNOWN would clear offline_since tracking and make an
    unavailable camera read as available again on a transient probe blip
    (bug-hunt 2026-07-27, Copilot review round 5).
    """
    coordinator = SimpleNamespace(
        should_check_status=lambda cam_id, now, interval: True,
        cached_status={"CAM1": "OFFLINE"},
        async_local_tcp_ping=AsyncMock(return_value=False),
        offline_since={"CAM1": 0.0},
        per_cam_status_at={},
    )
    session = MagicMock()

    class _Raiser:
        async def __aenter__(self):
            raise aiohttp.ClientError("boom")

        async def __aexit__(self, *exc):
            return None

    session.get = MagicMock(return_value=_Raiser())

    _cam_id, status = await _check_one_camera_status(
        coordinator, "CAM1", session, {}, now=100.0, interval_status=60
    )
    assert status == "OFFLINE"
    # Preserved OFFLINE status must keep offline_since tracking intact.
    assert "CAM1" in coordinator.offline_since
