"""Tests for coordinator.py's pure helper functions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.camera_status import (
    _check_one_camera_status,
)
from homeassistant.components.bosch_shc_camera.const import CLOUD_API, DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import (
    BoschCameraCoordinator,
    _is_safe_bosch_host,
    _is_safe_local_camera_host,
    _parse_safe_rcp_proxy_url,
    get_options,
)
from homeassistant.components.bosch_shc_camera.tick_housekeeping import run_housekeeping
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


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


def test_is_safe_bosch_host_rejects_userinfo_smuggled_host() -> None:
    """Reject any "@" outright — a legitimate Bosch value never contains one.

    A naive rsplit(":", 1) on this value yields the allowlisted-looking
    "proxy.boschsecurity.com", but an HTTP client parses "user:pass@host"
    authority syntax and actually connects to attacker.example. Even where
    the real connection target IS the safe host (userinfo before "@"),
    aiohttp turns that userinfo into a Basic-Auth header sent to Bosch's
    real proxy — reject unconditionally instead of relying on
    userinfo-vs-host semantics (Copilot review round 18, PR #176545).
    """
    assert _is_safe_bosch_host("proxy.boschsecurity.com:443@attacker.example") is False
    assert _is_safe_bosch_host("attacker.example@proxy.boschsecurity.com") is False


def test_is_safe_bosch_host_rejects_malformed_ipv6_bracket() -> None:
    """urlparse() can raise ValueError on malformed input — fail closed.

    The old rsplit(":", 1) implementation could never raise; a value like
    "[::1" now must not propagate a ValueError past the caller's narrower
    except (TimeoutError, aiohttp.ClientError) (Copilot review round 18).
    """
    assert _is_safe_bosch_host("[::1") is False


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


def test_is_safe_local_camera_host_rejects_loopback_and_unspecified() -> None:
    """A poisoned cache/cloud response must not connect HA back to itself.

    Python's `ipaddress.is_private` is also true for loopback and
    unspecified addresses — both must be excluded explicitly (Copilot
    review round 19, PR #176545).
    """
    assert _is_safe_local_camera_host("127.0.0.1:443") is False
    assert _is_safe_local_camera_host("0.0.0.0:443") is False


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


class TestAsyncPutCameraRetryStatus:
    """`async_put_camera`'s retry must accept the same success statuses.

    The post-401-refresh retry must accept the same success status set
    (200/201/204) as the initial attempt — it's the identical write, not
    a different semantic operation (Copilot review round 9).
    """

    def _bind(self, coord: SimpleNamespace) -> SimpleNamespace:
        coord.async_put_camera = BoschCameraCoordinator.async_put_camera.__get__(coord)
        return coord

    def _make_coord(self) -> SimpleNamespace:
        return SimpleNamespace(token="old-tok", hass=MagicMock())

    @staticmethod
    def _put_side_effect(first_status: int, retry_status: int):
        first_resp = MagicMock()
        first_resp.status = first_status
        retry_resp = MagicMock()
        retry_resp.status = retry_status
        call_count = [0]

        def _put_cm(*_args: object, **_kwargs: object) -> MagicMock:
            call_count[0] += 1
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(
                return_value=first_resp if call_count[0] == 1 else retry_resp
            )
            cm.__aexit__ = AsyncMock(return_value=None)
            return cm

        return _put_cm

    @pytest.mark.asyncio
    async def test_401_then_201_on_retry_returns_true(self) -> None:
        """A 201 on the post-refresh retry must return True."""
        coord = self._bind(self._make_coord())
        coord.ensure_valid_token = AsyncMock(return_value="new-tok")

        session = MagicMock()
        session.put = MagicMock(side_effect=self._put_side_effect(401, 201))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is True, "A 201 on the post-refresh retry must return True"

    @pytest.mark.asyncio
    async def test_401_then_200_on_retry_returns_true(self) -> None:
        """A 200 on the post-refresh retry must still work (regression guard)."""
        coord = self._bind(self._make_coord())
        coord.ensure_valid_token = AsyncMock(return_value="new-tok")

        session = MagicMock()
        session.put = MagicMock(side_effect=self._put_side_effect(401, 200))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is True


def test_persist_cloud_outage_flag_uses_spawn_tracked() -> None:
    """The cloud-outage-notified dedup flag save must go through spawn_tracked.

    An untracked `hass.async_create_task` save can still complete after
    config-entry removal deletes the Store, recreating integration-owned
    state on disk after removal — bypassing the teardown behavior
    `spawn_tracked()` documents (Copilot review round 10).
    """
    store = MagicMock()
    store.async_save = MagicMock()
    coord = SimpleNamespace(
        cloud_alert_store=store,
        cloud_outage_notified=True,
        spawn_tracked=MagicMock(),
    )
    coord._persist_cloud_outage_flag = (
        BoschCameraCoordinator._persist_cloud_outage_flag.__get__(coord)
    )

    coord._persist_cloud_outage_flag()

    coord.spawn_tracked.assert_called_once()
    _, call_kwargs = coord.spawn_tracked.call_args
    assert call_kwargs["name"] == "bosch_shc_camera_persist_cloud_outage_flag"
    store.async_save.assert_called_once_with({"outage_notified": True})


def test_persist_cloud_outage_flag_no_store_configured_skips() -> None:
    """No `cloud_alert_store` attribute at all must not raise."""
    coord = SimpleNamespace(spawn_tracked=MagicMock())
    coord._persist_cloud_outage_flag = (
        BoschCameraCoordinator._persist_cloud_outage_flag.__get__(coord)
    )

    coord._persist_cloud_outage_flag()  # must not raise

    coord.spawn_tracked.assert_not_called()


class TestCloudApiOverrideValidation:
    """`cloud_api_override` validation against the Bosch-domain allowlist.

    It has no UI in this (Core) config flow — it can only ever be legacy
    data inherited from a HACS-migrated entry, so it must be validated
    before use: every request built from `self._cloud_api` attaches the
    real bearer token, and an unvalidated override could exfiltrate it to
    an arbitrary host (Copilot review round 11).
    """

    def _make_entry(self, cloud_api_override: str) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={
                "bearer_token": "tok",
                "refresh_token": "rtok",
                "cloud_api_override": cloud_api_override,
            },
            options={},
        )

    async def test_safe_bosch_override_is_used(self, hass: HomeAssistant) -> None:
        """A real Bosch-domain override is accepted and used as-is."""
        entry = self._make_entry("https://staging.boschsecurity.com")
        entry.add_to_hass(hass)

        coord = BoschCameraCoordinator(hass, entry)

        assert coord._cloud_api == "https://staging.boschsecurity.com"

    async def test_unsafe_override_falls_back_to_default(
        self, hass: HomeAssistant
    ) -> None:
        """A non-Bosch override is rejected, falling back to the default API."""
        entry = self._make_entry("https://evil.example.com")
        entry.add_to_hass(hass)

        coord = BoschCameraCoordinator(hass, entry)

        assert coord._cloud_api == CLOUD_API

    async def test_no_override_uses_default(self, hass: HomeAssistant) -> None:
        """No override at all uses the default API, as before."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={"bearer_token": "tok", "refresh_token": "rtok"},
            options={},
        )
        entry.add_to_hass(hass)

        coord = BoschCameraCoordinator(hass, entry)

        assert coord._cloud_api == CLOUD_API


class TestPrivacyDriftForcesRefresh:
    """`_async_fetch_live_snapshot_impl`'s privacy-state-drift detection.

    An empty snap.jpg body while HA's own cached privacy state is OFF
    means the camera's privacy mode was toggled via the Bosch app and the
    cloud poll hasn't caught up yet — the WARNING promises "forcing
    refresh", which must go through `spawn_tracked` (not a bare
    `hass.async_create_task`), or it can outlive config-entry unload and
    run against an already-torn-down coordinator (Copilot review
    round 12).
    """

    @staticmethod
    def _resp_cm(status: int, body: bytes = b"", content_type: str = "") -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.headers = {"Content-Type": content_type}
        resp.read = AsyncMock(return_value=body)
        resp.text = AsyncMock(return_value="")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    @pytest.mark.asyncio
    async def test_empty_body_with_ha_privacy_off_uses_spawn_tracked(self) -> None:
        """Drift-forced refresh must go through spawn_tracked, not a bare task."""
        coord = SimpleNamespace(
            token="tok",
            hass=MagicMock(),
            shc_state_cache={},
            _proxy_url_cache={
                CAM_ID: (
                    "proxy-01.live.cbs.boschsecurity.com:42090/hash",
                    9_999_999_999.0,
                )
            },
            _rcp_099e_probe_failed_until={},
            hw_version={},
            data={CAM_ID: {"privacyMode": "OFF"}},
            async_request_refresh=AsyncMock(),
            spawn_tracked=MagicMock(side_effect=lambda coro, **_kw: coro.close()),
        )
        coord._async_fetch_live_snapshot_impl = (
            BoschCameraCoordinator._async_fetch_live_snapshot_impl.__get__(coord)
        )

        session = MagicMock()
        session.get = MagicMock(
            return_value=self._resp_cm(200, body=b"", content_type="image/jpeg")
        )
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=session_cm,
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None
        coord.spawn_tracked.assert_called_once()
        _, call_kwargs = coord.spawn_tracked.call_args
        assert call_kwargs["name"] == "bosch_shc_camera_privacy_drift_refresh"


class TestFetchLiveSnapshotLocalUsesPooledSession:
    """The LOCAL-bootstrap PUT must reuse the pooled Bosch cloud session.

    `async_fetch_live_snapshot_local` must use `async_bosch_cloud_session_cm`
    instead of opening a fresh connector/TLS handshake on every call —
    otherwise every REMOTE-401 fallback attempt (e.g. CAMERA_360) pays a
    full TCP+TLS handshake cost instead of reusing the pool the rest of the
    integration already established (Copilot review round 14).
    """

    @pytest.mark.asyncio
    async def test_put_local_uses_shared_session_cm(self) -> None:
        """PUT LOCAL must go through the shared session context manager."""
        coord = SimpleNamespace(
            token="tok",
            hass=MagicMock(),
            shc_state_cache={},
            get_quality_params=MagicMock(return_value=(True, 0)),
        )
        coord.async_fetch_live_snapshot_local = (
            BoschCameraCoordinator.async_fetch_live_snapshot_local.__get__(coord)
        )

        resp = MagicMock()
        resp.status = 404  # any non-(200,201) short-circuits before urls parsing
        resp.text = AsyncMock(return_value="{}")
        resp_cm = MagicMock()
        resp_cm.__aenter__ = AsyncMock(return_value=resp)
        resp_cm.__aexit__ = AsyncMock(return_value=None)

        session = MagicMock()
        session.put = MagicMock(return_value=resp_cm)
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=session_cm,
        ) as mock_session_cm:
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None
        mock_session_cm.assert_called_once_with(coord.hass)
        session.put.assert_called_once()


class TestLocalTcpPingRejectsUnsafeHost:
    """Must reject an unsafe/public host before ever opening a connection.

    `rcp_lan_ip_cache` is populated from RCP data returned via the cloud
    proxy and restored unvalidated from storage — unlike
    `local_creds_cache`, whose host is validated at every write site, this
    cache had no equivalent guard before a raw `asyncio.open_connection`
    call in `async_local_tcp_ping` (Copilot review round 14).
    """

    @pytest.mark.asyncio
    async def test_public_ip_never_reaches_open_connection(self) -> None:
        """A public IP must never reach asyncio.open_connection."""
        coord = SimpleNamespace(
            rcp_lan_ip_cache={CAM_ID: "8.8.8.8"},
            local_creds_cache={},
            lan_tcp_reachable={},
        )
        coord.get_cam_lan_ip = BoschCameraCoordinator.get_cam_lan_ip.__get__(coord)
        coord.async_local_tcp_ping = (
            BoschCameraCoordinator.async_local_tcp_ping.__get__(coord)
        )

        with patch("asyncio.open_connection") as mock_open_connection:
            result = await coord.async_local_tcp_ping(CAM_ID)

        assert result is False
        mock_open_connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_private_ip_reaches_open_connection(self) -> None:
        """A genuine private LAN IP still gets pinged normally."""
        coord = SimpleNamespace(
            rcp_lan_ip_cache={CAM_ID: "192.168.1.50"},
            local_creds_cache={},
            lan_tcp_reachable={},
        )
        coord.get_cam_lan_ip = BoschCameraCoordinator.get_cam_lan_ip.__get__(coord)
        coord.async_local_tcp_ping = (
            BoschCameraCoordinator.async_local_tcp_ping.__get__(coord)
        )

        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        with patch(
            "asyncio.open_connection", new=AsyncMock(return_value=(MagicMock(), writer))
        ) as mock_open_connection:
            result = await coord.async_local_tcp_ping(CAM_ID)

        assert result is True
        mock_open_connection.assert_called_once_with("192.168.1.50", 443)
