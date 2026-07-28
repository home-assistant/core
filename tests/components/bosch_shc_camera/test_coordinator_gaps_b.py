"""Regression tests for coordinator.py's upper-half patch-coverage gaps.

Targets stale-device cleanup, live-snapshot fetch (REMOTE + LOCAL), the RCP
session/read protocol, quality preference helpers, and `async_put_camera`'s
401-retry path.
"""

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"
OTHER_CAM_ID = "11112222-3333-4444-5555-666677778888"
PROXY_ENTRY = "proxy-01.live.cbs.boschsecurity.com:42090/hash123"


def _resp_cm(
    status: int, body: bytes = b"", content_type: str = "", text: str = ""
) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    resp.read = AsyncMock(return_value=body)
    resp.text = AsyncMock(return_value=text)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _session_cm(session: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "rtok"},
        options={},
    )


def _mock_entry_no_token() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={},
    )


class TestPurgeCamIdAndCleanupStaleDevices:
    """`_purge_cam_id` / `cleanup_stale_devices` purge per-cam state + devices."""

    async def test_purge_cam_id_clears_dict_and_set_entries(
        self, hass: HomeAssistant
    ) -> None:
        """Every dict/set attribute in the audited lists loses the cam_id."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        coord.local_creds_cache[CAM_ID] = {"user": "u"}
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        coord.slow_tier_deferred.add(CAM_ID)
        coord._notif_disabled_logged.add(CAM_ID)
        coord._fw_update_alerted.add(CAM_ID)

        coord._purge_cam_id(CAM_ID)

        assert CAM_ID not in coord.local_creds_cache
        assert CAM_ID not in coord.hw_version
        assert CAM_ID not in coord.slow_tier_deferred
        assert CAM_ID not in coord._notif_disabled_logged
        assert CAM_ID not in coord._fw_update_alerted

    async def test_purge_cam_id_is_noop_for_unknown_cam(
        self, hass: HomeAssistant
    ) -> None:
        """An unknown cam_id must not raise (`.pop`/`.discard` are safe)."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        coord._purge_cam_id("never-seen-cam")  # must not raise

    async def test_cleanup_stale_devices_removes_device_no_longer_in_account(
        self, hass: HomeAssistant, device_registry: dr.DeviceRegistry
    ) -> None:
        """A device whose cam_id vanished from the cloud account gets removed."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.local_creds_cache[CAM_ID] = {"user": "u"}

        dev_reg = device_registry
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, CAM_ID)},
            name="Stale Camera",
        )

        coord.cleanup_stale_devices(set())

        assert dev_reg.async_get(device.id) is None
        assert CAM_ID not in coord.local_creds_cache

    async def test_cleanup_stale_devices_keeps_device_still_in_account(
        self, hass: HomeAssistant, device_registry: dr.DeviceRegistry
    ) -> None:
        """A device whose cam_id is still current must survive untouched."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.local_creds_cache[CAM_ID] = {"user": "u"}

        dev_reg = device_registry
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, CAM_ID)},
            name="Current Camera",
        )

        coord.cleanup_stale_devices({CAM_ID})

        assert dev_reg.async_get(device.id) is not None
        assert coord.local_creds_cache[CAM_ID] == {"user": "u"}


class TestGetRcpSessionLock:
    """`_get_rcp_session_lock` gets-or-creates a per-proxy_hash lock."""

    async def test_returns_same_lock_for_same_proxy_hash(
        self, hass: HomeAssistant
    ) -> None:
        """Two lookups for the same proxy_hash return the identical lock."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        lock1 = coord._get_rcp_session_lock("hash-a")
        lock2 = coord._get_rcp_session_lock("hash-a")

        assert lock1 is lock2


class TestAsyncFetchLiveSnapshot:
    """`async_fetch_live_snapshot` serializes via a per-cam lock, delegating."""

    async def test_serializes_via_snapshot_lock(self, hass: HomeAssistant) -> None:
        """Acquires the per-cam lock and delegates to the impl method."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord._async_fetch_live_snapshot_impl = AsyncMock(return_value=b"jpeg-bytes")  # type: ignore[method-assign]

        result = await coord.async_fetch_live_snapshot(CAM_ID)

        assert result == b"jpeg-bytes"
        coord._async_fetch_live_snapshot_impl.assert_awaited_once_with(CAM_ID, None)
        assert CAM_ID in coord._snapshot_fetch_locks


class TestFetchLiveSnapshotImplNoToken:
    """No token at all short-circuits before any network call."""

    async def test_returns_none_without_token(self, hass: HomeAssistant) -> None:
        """No bearer token at all returns None before any network call."""
        entry = _mock_entry_no_token()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None


class TestFetchLiveSnapshotImplPrivacyShortCircuit:
    """Privacy-mode-ON short-circuits before opening a session."""

    async def test_privacy_mode_on_skips_network_call(
        self, hass: HomeAssistant
    ) -> None:
        """Privacy mode ON in the cache skips opening any cloud session."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.shc_state_cache[CAM_ID] = {"privacy_mode": True}

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm"
        ) as mock_session_cm:
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None
        mock_session_cm.assert_not_called()


class TestFetchLiveSnapshotImplProxyUrlCacheMiss:
    """Cache-miss path issues PUT /connection and caches urls[0]."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"  # gen2 → skip RCP 0x099e probe
        return coord

    async def test_put_connection_failure_status_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A non-(200,201) PUT /connection response yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(return_value=_resp_cm(500))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_put_connection_no_urls_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A 200 with an empty `urls` list yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(return_value=_resp_cm(200, text='{"urls": []}'))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_put_connection_unsafe_host_rejected(
        self, hass: HomeAssistant
    ) -> None:
        """A safe-domain-but-unsafe (e.g. metadata IP) proxy host is rejected."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(200, text='{"urls": ["169.254.169.254:80/hash"]}')
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_put_connection_success_fetches_snap_jpg(
        self, hass: HomeAssistant
    ) -> None:
        """A safe proxy host + a good snap.jpg response returns image bytes."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(200, text=f'{{"urls": ["{PROXY_ENTRY}"]}}')
        )
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8jpeg", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result == b"\xff\xd8jpeg"
        assert CAM_ID in coord._proxy_url_cache


class TestFetchLiveSnapshotImplProxyUrlCacheHit:
    """A warm, unexpired proxy cache entry skips PUT /connection."""

    async def test_cache_hit_skips_put_connection(self, hass: HomeAssistant) -> None:
        """A warm proxy-url cache entry is reused, skipping PUT /connection."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)

        session = MagicMock()
        session.put = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8jpeg", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result == b"\xff\xd8jpeg"
        session.put.assert_not_called()


class TestFetchLiveSnapshotImplProxyUrlCacheExpired:
    """An expired proxy-url cache entry is discarded and re-fetched via PUT."""

    async def test_expired_entry_is_purged_and_refetched(
        self, hass: HomeAssistant
    ) -> None:
        """A cache entry whose expiry is in the past triggers a fresh PUT /connection."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        # Expired (in the past) — must be dropped rather than reused.
        coord._proxy_url_cache[CAM_ID] = ("stale-proxy:1/hash", 1.0)

        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(200, text=f'{{"urls": ["{PROXY_ENTRY}"]}}')
        )
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8jpeg", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result == b"\xff\xd8jpeg"
        session.put.assert_called_once()
        assert coord._proxy_url_cache[CAM_ID][0] == PROXY_ENTRY


class TestFetchLiveSnapshotImplGen1Rcp099eProbe:
    """The Gen1 RCP 0x099e thumbnail probe: success, non-JPEG fallback, error."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "CAMERA_EYES"  # Gen1 — probe not skipped
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)
        return coord

    async def test_probe_returns_jpeg_bytes_directly(self, hass: HomeAssistant) -> None:
        """A real JPEG from RCP 0x099e is returned without touching snap.jpg."""
        coord = await self._make_coord(hass)
        coord.get_cached_rcp_session = AsyncMock(return_value="sess-1")  # type: ignore[method-assign]
        coord.rcp_read = AsyncMock(return_value=b"\xff\xd8thumb")  # type: ignore[method-assign]

        session = MagicMock()
        session.get = MagicMock()  # must not be called for snap.jpg

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID, jpeg_size=320)

        assert result == b"\xff\xd8thumb"
        session.get.assert_not_called()
        assert CAM_ID not in coord._rcp_099e_probe_failed_until

    async def test_probe_non_jpeg_response_falls_back_to_snap_jpg(
        self, hass: HomeAssistant
    ) -> None:
        """A non-JPEG RCP response memoizes failure and falls back to snap.jpg."""
        coord = await self._make_coord(hass)
        coord.get_cached_rcp_session = AsyncMock(return_value="sess-1")  # type: ignore[method-assign]
        coord.rcp_read = AsyncMock(return_value=b"<xml>not-a-jpeg</xml>")  # type: ignore[method-assign]

        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8full", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID, jpeg_size=320)

        assert result == b"\xff\xd8full"
        assert CAM_ID in coord._rcp_099e_probe_failed_until

    async def test_probe_exception_memoizes_failure_and_falls_back(
        self, hass: HomeAssistant
    ) -> None:
        """An exception during the RCP probe must not break snapshot fetch."""
        coord = await self._make_coord(hass)
        coord.get_cached_rcp_session = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8full", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID, jpeg_size=320)

        assert result == b"\xff\xd8full"
        assert CAM_ID in coord._rcp_099e_probe_failed_until

    async def test_memoized_failure_skips_probe_entirely(
        self, hass: HomeAssistant
    ) -> None:
        """Once memoized-failed, the probe is skipped for the remainder of the TTL."""
        coord = await self._make_coord(hass)
        coord._rcp_099e_probe_failed_until[CAM_ID] = math.inf
        coord.get_cached_rcp_session = AsyncMock()  # type: ignore[method-assign]

        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"\xff\xd8full", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID, jpeg_size=320)

        assert result == b"\xff\xd8full"
        coord.get_cached_rcp_session.assert_not_called()


class TestFetchLiveSnapshotImplSnapJpg404Retry:
    """A 404 on snap.jpg invalidates the cache and retries once."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)
        return coord

    async def test_404_then_fresh_lease_succeeds(self, hass: HomeAssistant) -> None:
        """A 404 invalidates the cache and a fresh lease then succeeds."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(404, content_type="text/plain"))
        session.put = MagicMock(
            return_value=_resp_cm(200, text=f'{{"urls": ["{PROXY_ENTRY}"]}}')
        )
        # After the retry PUT, the retried snap.jpg GET must succeed.
        retry_get_cm = _resp_cm(200, body=b"\xff\xd8retry", content_type="image/jpeg")
        session.get.side_effect = [
            _resp_cm(404, content_type="text/plain"),
            retry_get_cm,
        ]

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result == b"\xff\xd8retry"

    async def test_404_then_no_fresh_urls_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """The retry PUT returning no urls yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(404, content_type="text/plain"))
        session.put = MagicMock(return_value=_resp_cm(200, text='{"urls": []}'))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_404_then_unsafe_retry_host_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """The retry PUT returning an unsafe host is rejected."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(404, content_type="text/plain"))
        session.put = MagicMock(
            return_value=_resp_cm(200, text='{"urls": ["169.254.169.254:80/h"]}')
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_404_then_retry_non_200_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A non-200 status on the retried snap.jpg GET yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(200, text=f'{{"urls": ["{PROXY_ENTRY}"]}}')
        )
        session.get.side_effect = [
            _resp_cm(404, content_type="text/plain"),
            _resp_cm(500, content_type="text/plain"),
        ]

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None


class TestFetchLiveSnapshotImplEmptyBodyPrivacyAgree:
    """An empty snap.jpg body while HA already believes privacy is ON logs, no drift."""

    async def test_empty_body_with_ha_privacy_on_no_refresh_forced(
        self, hass: HomeAssistant
    ) -> None:
        """Both camera and HA agreeing privacy is ON must not force a refresh."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)
        coord.data = {CAM_ID: {"privacyMode": "ON"}}
        coord.spawn_tracked = MagicMock()  # type: ignore[method-assign]

        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, body=b"", content_type="image/jpeg")
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None
        coord.spawn_tracked.assert_not_called()


class TestFetchLiveSnapshotImplGenericFailureAndTimeout:
    """A non-200/non-404 snap.jpg response and a top-level timeout both yield None."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.hw_version[CAM_ID] = "HOME_Eyes_Outdoor"
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)
        return coord

    async def test_snap_jpg_500_returns_none(self, hass: HomeAssistant) -> None:
        """A generic non-404 failure status on snap.jpg yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(500, content_type="text/plain"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None

    async def test_client_error_during_fetch_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """An `aiohttp.ClientError` anywhere in the fetch yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord._async_fetch_live_snapshot_impl(CAM_ID)

        assert result is None


class TestFetchFreshEventSnapshot:
    """`async_fetch_fresh_event_snapshot`'s cache hit/miss + events fetch loop."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        return BoschCameraCoordinator(hass, entry)

    async def test_no_token_returns_none(self, hass: HomeAssistant) -> None:
        """No bearer token at all returns None before any network call."""
        entry = _mock_entry_no_token()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_cache_hit_skips_network(self, hass: HomeAssistant) -> None:
        """A warm, unexpired fresh-snap cache entry skips the network fetch."""
        coord = await self._make_coord(hass)
        coord._fresh_snap_cache[CAM_ID] = (b"cached-bytes", 9_999_999_999.0)

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session"
        ) as mock_get_session:
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result == b"cached-bytes"
        mock_get_session.assert_not_called()

    async def test_events_fetch_failure_returns_none(self, hass: HomeAssistant) -> None:
        """A non-200 status fetching the events list yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(500))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_no_events_returns_none(self, hass: HomeAssistant) -> None:
        """An empty events list yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, text="[]"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_event_without_image_url_is_skipped(
        self, hass: HomeAssistant
    ) -> None:
        """An event missing `imageUrl` is skipped, falling through to None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(200, text='[{"timestamp": "2026-07-28T00:00:00Z"}]')
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_unsafe_image_url_is_rejected(self, hass: HomeAssistant) -> None:
        """An event `imageUrl` on a non-Bosch domain is rejected."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(
            return_value=_resp_cm(
                200,
                text=(
                    '[{"imageUrl": "https://evil.example.com/img.jpg", '
                    '"timestamp": "2026-07-28T00:00:00Z"}]'
                ),
            )
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_safe_image_url_returns_bytes_and_caches(
        self, hass: HomeAssistant
    ) -> None:
        """A safe Bosch-domain `imageUrl` is fetched and cached."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        events_resp = _resp_cm(
            200,
            text=(
                '[{"imageUrl": "https://events.boschsecurity.com/img.jpg", '
                '"timestamp": "2026-07-28T00:00:00Z"}]'
            ),
        )
        img_resp = _resp_cm(200, body=b"event-jpeg")
        session.get = MagicMock(side_effect=[events_resp, img_resp])

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result == b"event-jpeg"
        assert coord._fresh_snap_cache[CAM_ID][0] == b"event-jpeg"

    async def test_top_level_client_error_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """The events GET raising a ClientError is caught by the outer handler."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result is None

    async def test_per_event_client_error_falls_through_to_next_event(
        self, hass: HomeAssistant
    ) -> None:
        """A per-event image fetch raising ClientError is skipped, not fatal."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        events_resp = _resp_cm(
            200,
            text=(
                '[{"imageUrl": "https://events.boschsecurity.com/first.jpg", '
                '"timestamp": "2026-07-28T00:00:00Z"}, '
                '{"imageUrl": "https://events.boschsecurity.com/second.jpg", '
                '"timestamp": "2026-07-28T00:00:01Z"}]'
            ),
        )
        img_resp = _resp_cm(200, body=b"second-event-jpeg")
        session.get = MagicMock(
            side_effect=[events_resp, aiohttp.ClientError("boom"), img_resp]
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_fetch_fresh_event_snapshot(CAM_ID)

        assert result == b"second-event-jpeg"

    async def test_lock_recheck_returns_cache_populated_while_waiting(
        self, hass: HomeAssistant
    ) -> None:
        """A concurrent caller populating the cache while we wait on the lock wins.

        Simulates the race: caller A holds the per-camera lock; caller B blocks
        on it after already missing the fast-path cache check. While B waits,
        A's fetch completes and populates `_fresh_snap_cache`. B must reuse
        that cached value once it acquires the lock, instead of fetching again.
        """
        coord = await self._make_coord(hass)
        lock = asyncio.Lock()
        coord._fresh_snap_locks[CAM_ID] = lock
        await lock.acquire()

        task = asyncio.ensure_future(coord.async_fetch_fresh_event_snapshot(CAM_ID))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        coord._fresh_snap_cache[CAM_ID] = (b"race-cached-bytes", 9_999_999_999.0)
        lock.release()

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session"
        ) as mock_get_session:
            result = await task

        assert result == b"race-cached-bytes"
        mock_get_session.assert_not_called()


class TestFetchLiveSnapshotLocal:
    """`async_fetch_live_snapshot_local`'s LOCAL PUT/Digest snap.jpg flow."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        return BoschCameraCoordinator(hass, entry)

    async def test_no_token_returns_none(self, hass: HomeAssistant) -> None:
        """No bearer token at all returns None before any network call."""
        entry = _mock_entry_no_token()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None

    async def test_privacy_mode_on_skips_network(self, hass: HomeAssistant) -> None:
        """Privacy mode ON in the cache skips opening any cloud session."""
        coord = await self._make_coord(hass)
        coord.shc_state_cache[CAM_ID] = {"privacy_mode": True}

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm"
        ) as mock_session_cm:
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None
        mock_session_cm.assert_not_called()

    async def test_put_connection_timeout_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A `ClientError` on the LOCAL PUT /connection yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(side_effect=aiohttp.ClientError("boom"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None

    async def test_missing_credentials_returns_none(self, hass: HomeAssistant) -> None:
        """A PUT /connection response missing user/password yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(200, text='{"urls": ["192.168.1.50:443"]}')
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None

    async def test_unsafe_local_host_rejected(self, hass: HomeAssistant) -> None:
        """A public-IP LOCAL host is rejected and never cached."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(
                200,
                text=('{"user": "u", "password": "p", "urls": ["8.8.8.8:443"]}'),
            )
        )

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
            return_value=_session_cm(session),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None
        assert CAM_ID.upper() not in coord.local_creds_cache

    async def test_successful_digest_fetch_returns_bytes_and_caches_creds(
        self, hass: HomeAssistant
    ) -> None:
        """A full success path returns image bytes and caches LOCAL creds."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(
                200,
                text=('{"user": "u", "password": "p", "urls": ["192.168.1.50:443"]}'),
            )
        )

        digest_resp = MagicMock()
        digest_resp.status = 200
        digest_resp.headers = {"Content-Type": "image/jpeg"}
        digest_resp.read = AsyncMock(return_value=b"local-jpeg")
        digest_cm = MagicMock()
        digest_cm.__aenter__ = AsyncMock(return_value=digest_resp)
        digest_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
                return_value=_session_cm(session),
            ),
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_digest_request",
                new=AsyncMock(return_value=digest_cm),
            ),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result == b"local-jpeg"
        assert coord.local_creds_cache[CAM_ID.upper()]["host"] == "192.168.1.50"
        assert coord.local_creds_cache[CAM_ID.upper()]["port"] == 443

    async def test_digest_fetch_bad_status_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A non-200 Digest snap.jpg response yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(
                200,
                text=('{"user": "u", "password": "p", "urls": ["192.168.1.50:443"]}'),
            )
        )

        digest_resp = MagicMock()
        digest_resp.status = 401
        digest_resp.headers = {"Content-Type": ""}
        digest_cm = MagicMock()
        digest_cm.__aenter__ = AsyncMock(return_value=digest_resp)
        digest_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
                return_value=_session_cm(session),
            ),
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_digest_request",
                new=AsyncMock(return_value=digest_cm),
            ),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None

    async def test_digest_fetch_value_error_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """Malformed/missing WWW-Authenticate (ValueError) must not raise."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.put = MagicMock(
            return_value=_resp_cm(
                200,
                text=('{"user": "u", "password": "p", "urls": ["192.168.1.50:443"]}'),
            )
        )

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_bosch_cloud_session_cm",
                return_value=_session_cm(session),
            ),
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_digest_request",
                new=AsyncMock(side_effect=ValueError("no WWW-Authenticate")),
            ),
        ):
            result = await coord.async_fetch_live_snapshot_local(CAM_ID)

        assert result is None


class TestRcpSessionLifecycle:
    """`_invalidate_rcp_session` / `get_cached_rcp_session` / `_rcp_session`."""

    async def test_invalidate_removes_cached_entry(self, hass: HomeAssistant) -> None:
        """Invalidating a cached proxy_hash removes it from the cache."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.rcp_session_cache["hash-a"] = ("sess-1", 9_999_999_999.0)

        coord._invalidate_rcp_session("hash-a")

        assert "hash-a" not in coord.rcp_session_cache

    async def test_invalidate_unknown_hash_is_noop(self, hass: HomeAssistant) -> None:
        """Invalidating a proxy_hash never cached must not raise."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        coord._invalidate_rcp_session("never-cached")  # must not raise

    async def test_get_cached_rcp_session_hit_skips_open(
        self, hass: HomeAssistant
    ) -> None:
        """A warm, unexpired session cache entry skips opening a new session."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.rcp_session_cache["hash-a"] = ("sess-cached", 9_999_999_999.0)
        coord._rcp_session = AsyncMock()  # type: ignore[method-assign]

        result = await coord.get_cached_rcp_session("proxy-host:1", "hash-a")

        assert result == "sess-cached"
        coord._rcp_session.assert_not_called()

    async def test_get_cached_rcp_session_expired_reopens(
        self, hass: HomeAssistant
    ) -> None:
        """An expired cache entry reopens a new session and re-caches it."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.rcp_session_cache["hash-a"] = ("sess-old", -1.0)
        coord._rcp_session = AsyncMock(return_value="sess-new")  # type: ignore[method-assign]

        result = await coord.get_cached_rcp_session("proxy-host:1", "hash-a")

        assert result == "sess-new"
        assert coord.rcp_session_cache["hash-a"][0] == "sess-new"

    async def test_get_cached_rcp_session_open_failure_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A failed session open returns None and does not cache anything."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord._rcp_session = AsyncMock(return_value=None)  # type: ignore[method-assign]

        result = await coord.get_cached_rcp_session("proxy-host:1", "hash-b")

        assert result is None
        assert "hash-b" not in coord.rcp_session_cache

    @pytest.mark.parametrize(
        ("step1_status", "sessionid_in_body", "expect_none"),
        [
            pytest.param(500, False, True, id="step1-http-error"),
            pytest.param(200, False, True, id="step1-no-sessionid-in-body"),
            pytest.param(200, True, False, id="step1-and-step2-succeed"),
        ],
    )
    async def test_rcp_session_handshake(
        self,
        hass: HomeAssistant,
        step1_status: int,
        sessionid_in_body: bool,
        expect_none: bool,
    ) -> None:
        """The 2-step RCP handshake succeeds, or fails at either step."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        body = "<sessionid>abc123</sessionid>" if sessionid_in_body else "<err/>"
        step1_resp = _resp_cm(step1_status, text=body)
        step2_resp = _resp_cm(200, text="<ack/>")

        session = MagicMock()
        session.get = MagicMock(side_effect=[step1_resp, step2_resp])
        client_session_cm = MagicMock()
        client_session_cm.__aenter__ = AsyncMock(return_value=session)
        client_session_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_ssl_context",
                new=AsyncMock(return_value=None),
            ),
            patch("aiohttp.TCPConnector", return_value=MagicMock(close=AsyncMock())),
            patch("aiohttp.ClientSession", return_value=client_session_cm),
        ):
            result = await coord._rcp_session("proxy-host:1", "hash-a")

        if expect_none:
            assert result is None
        else:
            assert result == "abc123"

    async def test_rcp_session_step1_client_error_returns_none(
        self, hass: HomeAssistant
    ) -> None:
        """A `ClientError` on the handshake's first step yields None."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))
        client_session_cm = MagicMock()
        client_session_cm.__aenter__ = AsyncMock(return_value=session)
        client_session_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_ssl_context",
                new=AsyncMock(return_value=None),
            ),
            patch("aiohttp.TCPConnector", return_value=MagicMock(close=AsyncMock())),
            patch("aiohttp.ClientSession", return_value=client_session_cm),
        ):
            result = await coord._rcp_session("proxy-host:1", "hash-a")

        assert result is None

    async def test_rcp_session_step2_client_error_still_returns_session_id(
        self, hass: HomeAssistant
    ) -> None:
        """Step 2 (ACK) failing must not discard an already-parsed sessionid."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        step1_resp = _resp_cm(200, text="<sessionid>abc123</sessionid>")
        session = MagicMock()
        session.get = MagicMock(
            side_effect=[step1_resp, aiohttp.ClientError("ack failed")]
        )
        client_session_cm = MagicMock()
        client_session_cm.__aenter__ = AsyncMock(return_value=session)
        client_session_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_ssl_context",
                new=AsyncMock(return_value=None),
            ),
            patch("aiohttp.TCPConnector", return_value=MagicMock(close=AsyncMock())),
            patch("aiohttp.ClientSession", return_value=client_session_cm),
        ):
            result = await coord._rcp_session("proxy-host:1", "hash-a")

        assert result == "abc123"


class TestProxyHashFromRcpBase:
    """`_proxy_hash_from_rcp_base` extracts the hash segment or returns None."""

    @pytest.mark.parametrize(
        ("rcp_base", "expected"),
        [
            pytest.param(
                "https://proxy-01.example.com:1/abcHash/rcp.xml",
                "abcHash",
                id="well-formed",
            ),
            pytest.param(
                "https://proxy-01.example.com:1/abcHash/other.xml",
                None,
                id="does-not-end-in-rcp-xml",
            ),
            pytest.param("not-a-url", None, id="malformed-single-segment"),
        ],
    )
    def test_extraction(self, rcp_base: str, expected: str | None) -> None:
        """Extracts the hash segment for a well-formed URL, else None."""
        assert BoschCameraCoordinator._proxy_hash_from_rcp_base(rcp_base) == expected


class TestRcpRead:
    """`rcp_read` READs an RCP command, invalidating the session on 401/403/0x0c0d."""

    async def _make_coord(self, hass: HomeAssistant) -> BoschCameraCoordinator:
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.rcp_session_cache["abcHash"] = ("sess-1", 9_999_999_999.0)
        return coord

    async def test_success_returns_raw_bytes(self, hass: HomeAssistant) -> None:
        """A 200 response returns the raw payload bytes."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, body=b"raw-payload"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.rcp_read(
                "https://proxy/abcHash/rcp.xml", "0x099e", "sess-1"
            )

        assert result == b"raw-payload"

    @pytest.mark.parametrize("status", [401, 403])
    async def test_auth_failure_invalidates_session(
        self, hass: HomeAssistant, status: int
    ) -> None:
        """A 401/403 response invalidates the cached RCP session."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(status))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.rcp_read(
                "https://proxy/abcHash/rcp.xml", "0x099e", "sess-1"
            )

        assert result is None
        assert "abcHash" not in coord.rcp_session_cache

    async def test_session_closed_error_invalidates_session(
        self, hass: HomeAssistant
    ) -> None:
        """An RCP `<err>0x0c0d</err>` body invalidates the cached session."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, body=b"<err>0x0c0d</err>"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.rcp_read(
                "https://proxy/abcHash/rcp.xml", "0x099e", "sess-1"
            )

        assert result is None
        assert "abcHash" not in coord.rcp_session_cache

    async def test_timeout_returns_none(self, hass: HomeAssistant) -> None:
        """A timeout during the RCP READ yields None."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(side_effect=TimeoutError())

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.rcp_read(
                "https://proxy/abcHash/rcp.xml", "0x099e", "sess-1"
            )

        assert result is None

    async def test_num_param_included_when_nonzero(self, hass: HomeAssistant) -> None:
        """A nonzero `num` argument is included in the RCP query params."""
        coord = await self._make_coord(hass)
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, body=b"data"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            await coord.rcp_read(
                "https://proxy/abcHash/rcp.xml", "0x0a36", "sess-1", num=4
            )

        _, call_kwargs = session.get.call_args
        assert call_kwargs["params"]["num"] == "4"


class TestAsyncUpdateRcpDataDelegates:
    """`_async_update_rcp_data` is a thin delegate to `rcp.async_update_rcp_data`."""

    async def test_delegates_with_same_args(self, hass: HomeAssistant) -> None:
        """Delegates to `rcp.async_update_rcp_data` with identical arguments."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_update_rcp_data",
            new=AsyncMock(),
        ) as mock_update:
            await coord._async_update_rcp_data(CAM_ID, "proxy-host:1", "hash-a")

        mock_update.assert_awaited_once_with(coord, CAM_ID, "proxy-host:1", "hash-a")


class TestRcpDataAccessors:
    """Simple cache-lookup accessors: clock_offset/rcp_lan_ip/product_name/bitrate."""

    async def test_accessors_return_cached_values_or_defaults(
        self, hass: HomeAssistant
    ) -> None:
        """Each accessor returns its cached value for a known cam, else default."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.rcp_clock_offset_cache[CAM_ID] = 1.5
        coord.rcp_lan_ip_cache[CAM_ID] = "192.168.1.50"
        coord.rcp_product_name_cache[CAM_ID] = "Eyes Outdoor II"
        coord.rcp_bitrate_cache[CAM_ID] = [512, 1024, 2048]

        assert coord.clock_offset(CAM_ID) == 1.5
        assert coord.clock_offset(OTHER_CAM_ID) is None
        assert coord.rcp_lan_ip(CAM_ID) == "192.168.1.50"
        assert coord.rcp_lan_ip(OTHER_CAM_ID) is None
        assert coord.rcp_product_name(CAM_ID) == "Eyes Outdoor II"
        assert coord.rcp_product_name(OTHER_CAM_ID) is None
        assert coord.rcp_bitrate_ladder(CAM_ID) == [512, 1024, 2048]
        assert coord.rcp_bitrate_ladder(OTHER_CAM_ID) == []


class TestQualityPreference:
    """`get_quality` / `set_quality` / `get_quality_params`."""

    async def test_get_quality_defaults_to_auto(self, hass: HomeAssistant) -> None:
        """No preference set yet defaults to 'auto'."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        assert coord.get_quality(CAM_ID) == "auto"

    async def test_set_quality_updates_preference_and_invalidates_proxy_cache(
        self, hass: HomeAssistant
    ) -> None:
        """Setting quality updates the preference and drops the proxy-url cache."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord._proxy_url_cache[CAM_ID] = (PROXY_ENTRY, 9_999_999_999.0)

        coord.set_quality(CAM_ID, "high")

        assert coord.get_quality(CAM_ID) == "high"
        assert CAM_ID not in coord._proxy_url_cache

    @pytest.mark.parametrize(
        ("quality", "expected"),
        [
            pytest.param("high", (True, 1), id="high"),
            pytest.param("low", (False, 4), id="low"),
            pytest.param("auto", (False, 2), id="auto"),
        ],
    )
    async def test_get_quality_params(
        self, hass: HomeAssistant, quality: str, expected: tuple[bool, int]
    ) -> None:
        """Each quality preference maps to its (highQualityVideo, inst) pair."""
        entry = _mock_entry()
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)
        coord.set_quality(CAM_ID, quality)

        assert coord.get_quality_params(CAM_ID) == expected


class TestAsyncPutCameraRetryTokenRefreshFailure:
    """`async_put_camera`'s 401-retry: token-refresh failure/cancellation paths."""

    def _bind(self, coord: SimpleNamespace) -> SimpleNamespace:
        coord.async_put_camera = BoschCameraCoordinator.async_put_camera.__get__(coord)
        return coord

    def _make_coord(self) -> SimpleNamespace:
        return SimpleNamespace(token="old-tok", hass=MagicMock())

    async def test_token_refresh_raises_generic_exception_returns_false(self) -> None:
        """A generic refresh failure must fail only this write, not propagate."""
        coord = self._bind(self._make_coord())
        coord.ensure_valid_token = AsyncMock(side_effect=RuntimeError("refresh boom"))

        session = MagicMock()
        session.put = MagicMock(return_value=_resp_cm(401))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is False

    async def test_token_refresh_cancelled_error_propagates(self) -> None:
        """A `CancelledError` during token refresh must re-raise, not be swallowed."""
        coord = self._bind(self._make_coord())
        coord.ensure_valid_token = AsyncMock(side_effect=asyncio.CancelledError())

        session = MagicMock()
        session.put = MagicMock(return_value=_resp_cm(401))

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
                new=AsyncMock(return_value=session),
            ),
            pytest.raises(asyncio.CancelledError),
        ):
            await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

    async def test_401_then_retry_failure_status_returns_false_and_logs_body(
        self,
    ) -> None:
        """A non-success status on the post-refresh retry logs the body and returns False."""
        coord = self._bind(self._make_coord())
        coord.ensure_valid_token = AsyncMock(return_value="new-tok")

        first_resp = _resp_cm(401)
        retry_resp = _resp_cm(500, text="server error detail")
        session = MagicMock()
        session.put = MagicMock(side_effect=[first_resp, retry_resp])

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is False

    async def test_non_401_failure_status_logs_body_and_returns_false(self) -> None:
        """A non-401 failure status (e.g. 500) on the initial attempt returns False."""
        coord = self._bind(self._make_coord())

        session = MagicMock()
        session.put = MagicMock(return_value=_resp_cm(500, text="boom detail"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is False

    async def test_client_error_returns_false(self) -> None:
        """An `aiohttp.ClientError` during the PUT returns False, does not raise."""
        coord = self._bind(self._make_coord())

        session = MagicMock()
        session.put = MagicMock(side_effect=aiohttp.ClientError("boom"))

        with patch(
            "homeassistant.components.bosch_shc_camera.coordinator.async_get_bosch_cloud_session",
            new=AsyncMock(return_value=session),
        ):
            result = await coord.async_put_camera(CAM_ID, "privacy", {"enabled": True})

        assert result is False
