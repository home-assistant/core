"""Regression tests closing patch-coverage gaps in camera.py.

Companion to test_camera.py — kept in a separate file to avoid collisions
with other agents editing the existing test module in parallel. Reuses
`_setup_camera_entity`/`CAM_ID`/`FAKE_COORDINATOR_DATA` from test_camera.py
rather than duplicating the config-entry setup boilerplate.
"""

import asyncio
from io import BytesIO
import math
import time
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from homeassistant.components.bosch_shc_camera.camera import (
    BoschCamera,
    _rotate_jpeg_180,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant

from .test_camera import CAM_ID, FAKE_COORDINATOR_DATA, _setup_camera_entity

from tests.common import MockConfigEntry

_CAMERA_MOD = "homeassistant.components.bosch_shc_camera.camera"
_COORDINATOR_MOD = "homeassistant.components.bosch_shc_camera.coordinator"


def _make_real_jpeg() -> bytes:
    """Build a real, decodable tiny JPEG (unlike the 1x1 placeholder, which is deliberately truncated)."""
    buf = BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _digest_cm(
    status: int, body: bytes = b"", content_type: str = "image/jpeg"
) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    resp.read = AsyncMock(return_value=body)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _http_cm(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read = AsyncMock(return_value=b"\xff\xd8event-jpeg")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ── _rotate_jpeg_180 success path (lines 100-102) ───────────────────────────


def test_rotate_jpeg_180_success_path_actually_encodes_rotated_image() -> None:
    """A genuinely decodable JPEG is rotated and re-encoded (not just echoed back).

    The existing test in test_camera.py uses the class's 1x1 `_PLACEHOLDER_JPEG`
    fixture, which PIL cannot actually decode (`OSError: broken data stream`) —
    that test unintentionally only ever exercises the except-branch fallback.
    This uses a real, decodable JPEG to hit the save()/getvalue() success path.
    """
    real_jpeg = _make_real_jpeg()
    rotated = _rotate_jpeg_180(real_jpeg)
    assert isinstance(rotated, bytes)
    assert rotated.startswith(b"\xff\xd8")
    assert rotated != real_jpeg


# ── async_setup_entry — snapshots disabled (lines 116-117) ──────────────────


async def test_setup_entry_skips_when_snapshots_disabled(hass: HomeAssistant) -> None:
    """`enable_snapshots: False` skips the whole camera platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={"enable_snapshots": False},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            f"{_COORDINATOR_MOD}.BoschCameraCoordinator._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(
            f"{_COORDINATOR_MOD}.BoschCameraCoordinator.async_fetch_live_snapshot",
            return_value=None,
        ),
        patch(
            f"{_COORDINATOR_MOD}.BoschCameraCoordinator.async_fetch_live_snapshot_local",
            return_value=None,
        ),
        patch(
            f"{_COORDINATOR_MOD}.BoschCameraCoordinator.async_fetch_fresh_event_snapshot",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.camera_entities == {}


# ── async_added_to_hass — restore persisted snapshot (lines 193-206) ───────


async def test_added_to_hass_restores_persisted_snapshot_from_disk(
    hass: HomeAssistant,
) -> None:
    """A snapshot persisted to disk is restored before the first live fetch completes."""
    persisted = b"\xff\xd8persisted-snapshot-bytes"
    with patch(f"{_CAMERA_MOD}.load_snapshot", AsyncMock(return_value=persisted)):
        entity = await _setup_camera_entity(hass)

    assert entity.cached_image == persisted


# ── _handle_coordinator_update spawns a proactive refresh (line 244) ───────


async def test_handle_coordinator_update_spawns_refresh_when_stale(
    hass: HomeAssistant,
) -> None:
    """A stale `last_image_fetch` (and no in-flight refresh) spawns a background refresh task."""
    entity = await _setup_camera_entity(hass)
    entity.last_image_fetch = 0.0  # far in the past — definitely stale
    entity._refresh_inflight = False

    with patch.object(
        entity, "async_trigger_image_refresh", AsyncMock(return_value=None)
    ):
        entity._handle_coordinator_update()
        await hass.async_block_till_done()

    assert entity._image_refresh_task is not None


# ── async_trigger_image_refresh — privacy mode skip (lines 283-286) ────────


async def test_trigger_image_refresh_skips_when_privacy_mode_on(
    hass: HomeAssistant,
) -> None:
    """Privacy mode ON skips the refresh entirely — no fetch calls are made."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": True}

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock()
    ) as mock_fetch:
        await entity.async_trigger_image_refresh()

    mock_fetch.assert_not_called()


# ── async_trigger_image_refresh — concurrent-call guard (lines 291-295) ────


async def test_trigger_image_refresh_skips_when_already_in_flight(
    hass: HomeAssistant,
) -> None:
    """A second concurrent call short-circuits via `_refresh_inflight`."""
    entity = await _setup_camera_entity(hass)
    entity._refresh_inflight = True

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock()
    ) as mock_fetch:
        await entity.async_trigger_image_refresh()

    mock_fetch.assert_not_called()


# ── async_trigger_image_refresh — quick event-snapshot seed (319-326) ──────


async def test_trigger_image_refresh_seeds_quick_event_snapshot(
    hass: HomeAssistant,
) -> None:
    """Holding only the placeholder seeds `cached_image` from a quick event snapshot first."""
    entity = await _setup_camera_entity(hass)
    assert entity.cached_image is entity._PLACEHOLDER_JPEG
    quick = b"\xff\xd8quick-event-seed"

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_fresh_event_snapshot",
            AsyncMock(return_value=quick),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
    ):
        await entity.async_trigger_image_refresh()

    assert entity.cached_image == quick


# ── async_trigger_image_refresh — slow-path success + TOCTOU (362-384) ─────


async def test_trigger_image_refresh_discards_frame_when_privacy_turns_on_mid_fetch(
    hass: HomeAssistant,
) -> None:
    """Privacy turning ON during the fetch discards the just-fetched frame (TOCTOU guard)."""
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"already-real-frame"  # skip the quick-seed branch

    async def _fetch_live(*_a: object, **_k: object) -> bytes:
        entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": True}
        return b"\xff\xd8new-frame-during-privacy-toggle"

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", side_effect=_fetch_live
    ):
        await entity.async_trigger_image_refresh()

    assert entity.cached_image == b"already-real-frame"


async def test_trigger_image_refresh_persists_and_notifies_image_entity_on_success(
    hass: HomeAssistant,
) -> None:
    """A successful background refresh persists to disk and notifies the image entity."""
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"already-real-frame"
    fresh = b"\xff\xd8fresh-background-frame"
    img_entity = MagicMock()
    img_entity.async_notify_refreshed = AsyncMock()
    entity.coordinator.image_entities[CAM_ID] = img_entity

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=fresh),
        ),
        patch(f"{_CAMERA_MOD}.save_snapshot", AsyncMock()) as mock_save,
    ):
        await entity.async_trigger_image_refresh()

    assert entity.cached_image == fresh
    mock_save.assert_called_once()
    img_entity.async_notify_refreshed.assert_called_once()


# ── async_trigger_image_refresh — keep last good frame (390-397) ───────────


async def test_trigger_image_refresh_keeps_last_good_frame_when_live_fetch_unavailable(
    hass: HomeAssistant,
) -> None:
    """Both REMOTE+LOCAL failing while already holding a real frame keeps that frame."""
    entity = await _setup_camera_entity(hass)
    real_frame = b"already-real-frame"
    entity.cached_image = real_frame
    old_fetch_ts = entity.last_image_fetch

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
    ):
        await entity.async_trigger_image_refresh()

    assert entity.cached_image == real_frame
    assert entity.last_image_fetch > old_fetch_ts


async def test_trigger_image_refresh_swallows_unexpected_exception(
    hass: HomeAssistant,
) -> None:
    """An unexpected exception mid-refresh (any fetch tier) is swallowed, not raised.

    A best-effort background refresh spanning multiple fetch tiers plus disk
    I/O must never crash the entity — the next coordinator tick retries.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"already-real-frame"  # skip the quick-seed branch

    with patch.object(
        entity.coordinator,
        "async_fetch_live_snapshot",
        AsyncMock(side_effect=RuntimeError("unexpected boom")),
    ):
        await entity.async_trigger_image_refresh()  # must not raise

    assert entity._refresh_inflight is False


# ── motion_detection_enabled — no settings yet (line 417) ──────────────────


async def test_motion_detection_enabled_false_when_settings_unknown(
    hass: HomeAssistant,
) -> None:
    """No motion settings fetched yet reads as disabled, not an error."""
    entity = await _setup_camera_entity(hass)
    with patch.object(entity.coordinator, "motion_settings", return_value={}):
        assert entity.motion_detection_enabled is False


# ── frame_interval — forced-refresh fast poll (lines 507-509) ──────────────


async def test_frame_interval_is_fast_during_forced_refresh(
    hass: HomeAssistant,
) -> None:
    """`_force_image_refresh` makes HA poll again almost immediately (0.1s)."""
    entity = await _setup_camera_entity(hass)
    entity._force_image_refresh = True
    assert entity.frame_interval == 0.1


async def test_frame_interval_is_idle_interval_when_not_forced(
    hass: HomeAssistant,
) -> None:
    """Outside a forced refresh, HA polls on the normal idle cadence."""
    entity = await _setup_camera_entity(hass)
    entity._force_image_refresh = False
    assert entity.frame_interval == 60.0


# ── available — camera mid-firmware-install (line 539) ─────────────────────


async def test_available_false_while_camera_is_updating(hass: HomeAssistant) -> None:
    """A camera mid-firmware-install (reboot window) is marked unavailable."""
    entity = await _setup_camera_entity(hass)
    with patch.object(entity.coordinator, "is_updating", return_value=True):
        assert entity.available is False


# ── async_camera_image — exception safety net (lines 619-627) ──────────────


async def test_async_camera_image_reraises_cancelled_error(hass: HomeAssistant) -> None:
    """A CancelledError from the impl must propagate, never be swallowed."""
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(
            entity,
            "_async_camera_image_impl",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await entity.async_camera_image()


async def test_async_camera_image_serves_placeholder_on_unexpected_exception(
    hass: HomeAssistant,
) -> None:
    """Any other uncaught exception falls back to a valid (placeholder) JPEG."""
    entity = await _setup_camera_entity(hass)
    with patch.object(
        entity, "_async_camera_image_impl", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_async_camera_image_unexpected_exception_fails_closed_when_privacy_unknown(
    hass: HomeAssistant,
) -> None:
    """A blind cached-image serve on exception must also fail closed.

    Regression test for a 3-agent bug-hunt finding on the HACS backport of
    this fix (2026-08-04): the wrapper's `except Exception` branch served
    `cached_image` unconditionally, bypassing the privacy_unknown gate
    every other blind-cache-serve point in _async_camera_image_impl
    respects.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with patch.object(
        entity, "_async_camera_image_impl", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


# ── async_camera_image — 180° rotation applied (line 635) ──────────────────


async def test_async_camera_image_applies_180_rotation_when_enabled(
    hass: HomeAssistant,
) -> None:
    """The Bild 180° drehen switch runs the rotation via the executor."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.image_rotation_180 = {CAM_ID: True}
    real_jpeg = _make_real_jpeg()

    with (
        patch.object(
            entity, "_async_camera_image_impl", AsyncMock(return_value=real_jpeg)
        ),
        patch(
            f"{_CAMERA_MOD}._rotate_jpeg_180", return_value=b"\xff\xd8rotated-sentinel"
        ) as mock_rotate,
    ):
        image = await entity.async_camera_image()

    mock_rotate.assert_called_once_with(real_jpeg)
    assert image == b"\xff\xd8rotated-sentinel"


# ── _async_camera_image_impl — tier-1a first-load success (734-742) ────────


async def test_camera_image_first_load_success_updates_shared_cache(
    hass: HomeAssistant,
) -> None:
    """A cold-cache full-resolution fetch success populates the shared cache."""
    entity = await _setup_camera_entity(hass)
    fresh = b"\xff\xd8first-load-frame"

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock(return_value=fresh)
    ):
        image = await entity.async_camera_image()

    assert image == fresh
    assert entity.cached_image == fresh


# ── _async_camera_image_impl — tier-1a fail, LOCAL outage success (754,819,821) ──


async def test_camera_image_first_load_both_fail_then_local_outage_snap_succeeds(
    hass: HomeAssistant,
) -> None:
    """Cold-cache fetch failing on both REMOTE+LOCAL falls through to the LOCAL outage snap."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "password": "cbs-pass",
        "host": "192.168.1.50",
        "port": 443,
    }
    outage_bytes = b"\xff\xd8local-outage-first-load"

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(
            f"{_CAMERA_MOD}.async_digest_request",
            AsyncMock(return_value=_digest_cm(200, outage_bytes)),
        ),
    ):
        image = await entity.async_camera_image()

    assert image == outage_bytes
    assert entity.last_image_fetch != -math.inf


# ── _async_camera_image_impl — tier-1b stale-cache success (800-801) ───────


async def test_camera_image_stale_cache_fresh_fetch_updates_shared_cache(
    hass: HomeAssistant,
) -> None:
    """A stale (but non-placeholder) cache successfully refetching updates the shared cache."""
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"stale-frame"
    entity.last_image_fetch = 0.0  # stale
    fresh2 = b"\xff\xd8refreshed-stale-cache-frame"

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock(return_value=fresh2)
    ):
        image = await entity.async_camera_image()

    assert image == fresh2
    assert entity.cached_image == fresh2


# ── _async_camera_image_impl — cache fresh, immediate return (line 817) ────


async def test_camera_image_fresh_cache_returns_immediately_without_fetching(
    hass: HomeAssistant,
) -> None:
    """A recently-fetched cache with a KNOWN-safe privacy state is served directly.

    Privacy state must be explicitly False here — an unknown privacy state
    forces a verification fetch regardless of cache freshness (see
    test_unknown_privacy_state_forces_live_verification_fetch in
    test_camera.py, Copilot review finding on PR #176545).
    """
    entity = await _setup_camera_entity(hass)
    fresh_frame = b"recently-fetched-frame"
    entity.cached_image = fresh_frame
    entity.last_image_fetch = time.monotonic()  # fresh — not stale
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": False}

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock()
    ) as mock_fetch:
        image = await entity.async_camera_image()

    assert image == fresh_frame
    mock_fetch.assert_not_called()


# ── _async_camera_image_impl — tier-3 cache raced in during tier-1a (831) ──


async def test_camera_image_tier3_serves_frame_raced_in_during_tier1a_fetch(
    hass: HomeAssistant,
) -> None:
    """A concurrent update landing a real frame mid-tier-1a-fetch is served via tier 3.

    Simulates a genuine (if narrow) real-world race: `async_trigger_image_refresh`
    running concurrently on the event loop could update `cached_image` while this
    fetch is in flight. `_async_local_outage_snap` returning nothing must then
    fall through to serving whatever is now cached, rather than assuming it is
    still the placeholder.
    """
    entity = await _setup_camera_entity(hass)
    raced_in_frame = b"\xff\xd8raced-in-during-fetch"
    # Known-safe privacy state — an unknown state would (correctly, per the
    # round-20 fail-closed fix) withhold this raced-in frame instead.
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": False}

    async def _fetch_live(*_a: object, **_k: object) -> None:
        entity.cached_image = raced_in_frame

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", side_effect=_fetch_live
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
    ):
        image = await entity.async_camera_image()

    assert image == raced_in_frame


# ── _async_camera_image_impl — tier-4 event snapshot loop (836-882) ────────


def _entity_with_events(entity: BoschCamera, events: list[dict[str, object]]) -> None:
    entity.coordinator.data[CAM_ID] = {
        **FAKE_COORDINATOR_DATA[CAM_ID],
        "events": events,
    }


async def test_camera_image_tier4_event_snapshot_success(hass: HomeAssistant) -> None:
    """A successful event-snapshot fetch is cached and returned (also exercises `_fmt_event_ts`)."""
    entity = await _setup_camera_entity(hass)
    # Known-safe privacy state — an unknown state would (correctly, per the
    # round-20 fail-closed fix) withhold this event snapshot too, since it's
    # independent of the camera's current live privacy state.
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": False}
    _entity_with_events(
        entity,
        [
            {
                "imageUrl": "https://cam.boschsecurity.com/e.jpg",
                "timestamp": "2026-07-28T10:00:00+02:00",
            }
        ],
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(return_value=_http_cm(200))
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    assert image == b"\xff\xd8event-jpeg"


async def test_camera_image_tier4_event_snapshot_withheld_when_privacy_unknown(
    hass: HomeAssistant,
) -> None:
    """Even the event-snapshot last resort must fail closed.

    Regression test for a 3-agent bug-hunt finding on the HACS backport of
    this fix (2026-08-04): unlike every other tier, this one fetches a
    STORED HISTORICAL motion-event JPEG — independent of the camera's
    current live privacy state, so it doesn't naturally short-circuit to
    empty/error while privacy is engaged the way a live camera fetch does.
    The event could predate privacy being enabled just as easily as a stale
    cached_image can.
    """
    entity = await _setup_camera_entity(hass)
    assert CAM_ID not in entity.coordinator.shc_state_cache
    _entity_with_events(
        entity,
        [
            {
                "imageUrl": "https://cam.boschsecurity.com/e.jpg",
                "timestamp": "2026-07-28T10:00:00+02:00",
            }
        ],
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(return_value=_http_cm(200))
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_camera_image_tier4_event_snapshot_401_returns_cached(
    hass: HomeAssistant,
) -> None:
    """A 401 on the event-snapshot URL logs a warning and returns whatever is cached.

    Cache is left as the (still-placeholder) default here so tier 1 (no
    cached image yet) is entered and, with no LOCAL creds configured, falls
    through tiers 2/3 to reach tier 4 — the real path a genuine cold start
    with an expired token takes.
    """
    entity = await _setup_camera_entity(hass)
    _entity_with_events(
        entity, [{"imageUrl": "https://cam.boschsecurity.com/e.jpg", "timestamp": None}]
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(return_value=_http_cm(401))
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    assert image is entity._PLACEHOLDER_JPEG


async def test_camera_image_tier4_event_snapshot_403_tries_next_event(
    hass: HomeAssistant,
) -> None:
    """An expired-URL status (403/404/410) on one event tries the next event in the list."""
    entity = await _setup_camera_entity(hass)
    entity.last_image_fetch = 0.0
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": False}
    _entity_with_events(
        entity,
        [
            {
                "imageUrl": "https://cam.boschsecurity.com/expired.jpg",
                "timestamp": None,
            },
            {"imageUrl": "https://cam.boschsecurity.com/good.jpg", "timestamp": None},
        ],
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(side_effect=[_http_cm(403), _http_cm(200)])
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    assert image == b"\xff\xd8event-jpeg"
    assert session.get.call_count == 2


async def test_camera_image_tier4_event_snapshot_skips_event_missing_image_url(
    hass: HomeAssistant,
) -> None:
    """An event with no `imageUrl` at all is skipped (falls through to the placeholder)."""
    entity = await _setup_camera_entity(hass)
    _entity_with_events(entity, [{"imageUrl": None, "timestamp": None}])

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(return_value=_http_cm(200))
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    session.get.assert_not_called()
    assert image is entity._PLACEHOLDER_JPEG


async def test_camera_image_tier4_event_snapshot_unsafe_url_rejected(
    hass: HomeAssistant,
) -> None:
    """A non-Bosch imageUrl is rejected outright, never fetched."""
    entity = await _setup_camera_entity(hass)
    entity.last_image_fetch = 0.0
    _entity_with_events(
        entity, [{"imageUrl": "https://evil.example.com/e.jpg", "timestamp": None}]
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()
        session.get = MagicMock(return_value=_http_cm(200))
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    session.get.assert_not_called()
    assert image is entity._PLACEHOLDER_JPEG


async def test_camera_image_tier4_event_snapshot_network_error_swallowed(
    hass: HomeAssistant,
) -> None:
    """A transient network error on the event-snapshot fetch is swallowed, not raised."""
    entity = await _setup_camera_entity(hass)
    entity.last_image_fetch = 0.0
    _entity_with_events(
        entity, [{"imageUrl": "https://cam.boschsecurity.com/e.jpg", "timestamp": None}]
    )

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            AsyncMock(return_value=None),
        ),
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot_local",
            AsyncMock(return_value=None),
        ),
        patch(f"{_CAMERA_MOD}.async_get_bosch_cloud_session") as mock_session_factory,
    ):
        session = MagicMock()

        def _raise(*_a: object, **_k: object) -> None:
            raise TimeoutError

        session.get = MagicMock(side_effect=_raise)
        mock_session_factory.return_value = session
        image = await entity.async_camera_image()

    assert image is entity._PLACEHOLDER_JPEG


# ── _async_local_outage_snap — incomplete creds (line 912) ─────────────────


async def test_local_outage_snap_returns_none_when_creds_incomplete(
    hass: HomeAssistant,
) -> None:
    """Cached creds missing a password (or user/host) short-circuit to None."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "host": "192.168.1.50",
        # no "password"
    }
    session = MagicMock()

    result = await entity._async_local_outage_snap(session, None)

    assert result is None


# ── _async_local_outage_snap — network error (lines 933-935) ───────────────


async def test_local_outage_snap_returns_none_on_network_error(
    hass: HomeAssistant,
) -> None:
    """A ClientError/TimeoutError talking to the camera returns None, never raises."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "password": "cbs-pass",
        "host": "192.168.1.50",
        "port": 443,
    }

    def _raise(*_a: object, **_k: object) -> None:
        raise TimeoutError

    with patch(f"{_CAMERA_MOD}.async_digest_request", AsyncMock(side_effect=_raise)):
        result = await entity._async_local_outage_snap(MagicMock(), None)

    assert result is None


# ── _async_local_outage_snap — thumbnail request must not poison the shared
# full-resolution cache (Copilot review round 15) ───────────────────────────


async def test_local_outage_snap_thumbnail_request_does_not_update_shared_cache(
    hass: HomeAssistant,
) -> None:
    """A width=N (thumbnail) outage snap returns its bytes but leaves cached_image/last_image_fetch untouched.

    Mirrors the guard already applied to the tier-1/tier-2 fetch paths in
    `_async_camera_image_impl` (bug-hunt 2026-07-27) — `_async_local_outage_snap`
    itself was missed by that earlier fix, since it is a shared helper called
    from all three failure points regardless of requested resolution.
    """
    entity = await _setup_camera_entity(hass)
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "password": "cbs-pass",
        "host": "192.168.1.50",
        "port": 443,
    }
    sentinel_cached = b"already-cached-full-res-frame"
    sentinel_fetch_time = time.monotonic() - 3600
    entity.cached_image = sentinel_cached
    entity.last_image_fetch = sentinel_fetch_time
    thumb_bytes = b"\xff\xd8thumbnail-outage-frame"

    with patch(
        f"{_CAMERA_MOD}.async_digest_request",
        AsyncMock(return_value=_digest_cm(200, thumb_bytes)),
    ):
        result = await entity._async_local_outage_snap(MagicMock(), 320)

    assert result == thumb_bytes
    assert entity.cached_image == sentinel_cached
    assert entity.last_image_fetch == sentinel_fetch_time


async def test_local_outage_snap_full_resolution_request_updates_shared_cache(
    hass: HomeAssistant,
) -> None:
    """A req_jpeg_size=None (full-resolution) outage snap DOES update the shared cache."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "password": "cbs-pass",
        "host": "192.168.1.50",
        "port": 443,
    }
    entity.cached_image = b"stale-full-res-frame"
    sentinel_fetch_time = time.monotonic() - 3600
    entity.last_image_fetch = sentinel_fetch_time
    full_bytes = b"\xff\xd8full-resolution-outage-frame"

    with patch(
        f"{_CAMERA_MOD}.async_digest_request",
        AsyncMock(return_value=_digest_cm(200, full_bytes)),
    ):
        result = await entity._async_local_outage_snap(MagicMock(), None)

    assert result == full_bytes
    assert entity.cached_image == full_bytes
    assert entity.last_image_fetch != sentinel_fetch_time
