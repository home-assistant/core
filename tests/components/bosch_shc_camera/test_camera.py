"""Tests for camera.py's BoschCamera entity behavior."""

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.camera import (
    PRIVACY_UNKNOWN_RETRY_SEC,
    BoschCamera,
    _rotate_jpeg_180,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"

FAKE_COORDINATOR_DATA = {
    CAM_ID: {
        "info": {
            "title": "Front Door",
            "hardwareVersion": "HOME_Eyes_Outdoor",
            "firmwareVersion": "9.40.104",
            "macAddress": "aa:bb:cc:dd:ee:ff",
        },
        "status": "ONLINE",
        "events": [],
        "motion": {"enabled": False, "motionAlarmConfiguration": "HIGH"},
    }
}

_COORDINATOR_PATH = (
    "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
)


async def _setup_camera_entity(hass: HomeAssistant) -> BoschCamera:
    """Set up a config entry with one fake camera and return its entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            f"{_COORDINATOR_PATH}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{_COORDINATOR_PATH}.async_fetch_live_snapshot", return_value=None),
        patch(
            f"{_COORDINATOR_PATH}.async_fetch_live_snapshot_local", return_value=None
        ),
        patch(
            f"{_COORDINATOR_PATH}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry.runtime_data.camera_entities[CAM_ID]  # type: ignore[no-any-return]


async def test_available_false_when_coordinator_update_failed(
    hass: HomeAssistant,
) -> None:
    """A definitively-down coordinator (no LAN reachability confirmed either) is unavailable."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.last_update_success = False

    assert entity.available is False


async def test_available_true_during_cloud_outage_when_lan_reachable(
    hass: HomeAssistant,
) -> None:
    """A cloud-degraded startup with this camera confirmed LAN-reachable must still be available.

    `_async_first_refresh_with_fallback` sets `last_update_success = False`
    on a cloud-side failure and rehydrates cameras from the entity
    registry so LAN-only paths can take over — without also honoring
    `lan_tcp_reachable` here, the camera stayed marked unavailable for the
    whole outage and Home Assistant never even attempted the LAN-backed
    snapshot fetch (Copilot review round 10).
    """
    entity = await _setup_camera_entity(hass)
    entity.coordinator.last_update_success = False
    entity.coordinator.lan_tcp_reachable[CAM_ID] = (True, time.monotonic())

    assert entity.available is True


async def test_available_false_during_cloud_outage_when_lan_unreachable(
    hass: HomeAssistant,
) -> None:
    """A cloud-degraded startup where LAN ping also failed stays unavailable."""
    entity = await _setup_camera_entity(hass)
    entity.coordinator.last_update_success = False
    entity.coordinator.lan_tcp_reachable[CAM_ID] = (False, time.monotonic())

    assert entity.available is False


def test_rotate_jpeg_180_returns_bytes_for_a_real_jpeg() -> None:
    """A valid JPEG is rotated and re-encoded, producing new (still JPEG) bytes."""
    # 1x1 black JPEG — same fixture BoschCamera._PLACEHOLDER_JPEG uses.
    placeholder = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff"
        b"\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r"
        b"\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' "
        b"\",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01"
        b"\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T"
        b"\xdf\xb2\x80\x01\xff\xd9"
    )
    rotated = _rotate_jpeg_180(placeholder)
    assert isinstance(rotated, bytes)
    assert rotated.startswith(b"\xff\xd8")  # still a valid JPEG (SOI marker)


def test_rotate_jpeg_180_returns_original_bytes_on_decode_failure() -> None:
    """Non-JPEG bytes fail to decode and the original bytes are returned unchanged."""
    garbage = b"not a jpeg at all"
    assert _rotate_jpeg_180(garbage) == garbage


async def test_privacy_mode_returns_placeholder_instead_of_stale_cached_frame(
    hass: HomeAssistant,
) -> None:
    """Privacy mode ON serves the placeholder, never the last real scene before privacy engaged."""
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = (
        time.monotonic()
    )  # fresh — would normally short-circuit to cached_image
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": True}

    image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_forces_live_verification_fetch(
    hass: HomeAssistant,
) -> None:
    """Once the throttle window has elapsed, an unknown privacy state must not shortcut to a stale cached frame.

    On a cloud-degraded restart, shc_state_cache starts empty (privacy state
    unknown) while a cached real JPEG exists. Regression test for a Copilot
    review finding on PR #176545 (2026-07-31): the old code's `else: return
    self.cached_image` fast path served that pre-privacy frame with zero
    verification whenever the cache looked fresh. The fix forces a live-fetch
    attempt (proven here by asserting the fresh bytes it returns are served)
    once PRIVACY_UNKNOWN_RETRY_SEC has elapsed since the last attempt —
    throttled rather than on every single request (see the throttle-window
    test below), so an ongoing outage can't defeat CLOUD_SNAP_CACHE_TTL's
    backoff entirely.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = time.monotonic() - PRIVACY_UNKNOWN_RETRY_SEC
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with patch.object(
        entity.coordinator,
        "async_fetch_live_snapshot",
        return_value=b"freshly-verified-frame",
    ) as mock_fetch:
        image = await entity.async_camera_image()

    mock_fetch.assert_awaited_once()
    assert image == b"freshly-verified-frame"


async def test_unknown_privacy_state_throttled_within_retry_window(
    hass: HomeAssistant,
) -> None:
    """Within the retry window, an unknown privacy state must not force a re-fetch.

    Otherwise a sustained outage (or a camera whose cloud payload never
    carries privacyMode) would re-run the full REMOTE+LOCAL fetch chain on
    every single camera-proxy request, defeating CLOUD_SNAP_CACHE_TTL's
    backoff entirely. But not re-fetching must not mean trusting the stale
    cached frame either — serve the placeholder for the whole throttle
    window, not just the single request that attempted verification (a
    real bug caught by a 3-agent bug-hunt on the round-20 fail-closed fix:
    the fail-closed return path stamps last_image_fetch even on failure so
    the throttle itself can engage, which meant the very NEXT request
    within the window used to see cache_stale go False and fall straight
    into the old unconditional `else: return self.cached_image`).
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = time.monotonic()
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with patch.object(
        entity.coordinator, "async_fetch_live_snapshot", AsyncMock()
    ) as mock_fetch:
        image = await entity.async_camera_image()

    mock_fetch.assert_not_called()
    assert image == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_stays_fail_closed_across_two_requests(
    hass: HomeAssistant,
) -> None:
    """A failed verification must not unlock the stale frame on the very next request.

    Direct end-to-end regression test for the bug fixed above: request 1
    attempts verification (fails, stamps last_image_fetch, serves the
    placeholder); request 2 arrives moments later — inside the throttle
    window created by that very stamp — and must still serve the
    placeholder, not the withheld cached frame.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = time.monotonic() - PRIVACY_UNKNOWN_RETRY_SEC
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ) as mock_fetch,
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
        patch.object(entity, "_async_local_outage_snap", return_value=None),
    ):
        first = await entity.async_camera_image()
        second = await entity.async_camera_image()

    assert mock_fetch.await_count == 1, (
        "Request 2 must not re-attempt verification within the throttle window"
    )
    assert first == entity._PLACEHOLDER_JPEG
    assert second == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_falls_back_to_placeholder_when_no_cache(
    hass: HomeAssistant,
) -> None:
    """Unknown privacy state + no real cached frame + failed fetch → placeholder, not None."""
    entity = await _setup_camera_entity(hass)
    entity.cached_image = entity._PLACEHOLDER_JPEG
    entity.last_image_fetch = time.monotonic() - PRIVACY_UNKNOWN_RETRY_SEC
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ) as mock_fetch,
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
    ):
        image = await entity.async_camera_image()

    mock_fetch.assert_awaited_once()
    assert image == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_fails_closed_when_verification_fetch_fails(
    hass: HomeAssistant,
) -> None:
    """A failed verification attempt must not fall back to the stale cached frame.

    Regression test for a suppressed Copilot finding on PR #176545
    (2026-08-04, round 20): privacy_unknown only forced a fetch *attempt* —
    if that attempt (REMOTE + LOCAL + outage snap all failing) didn't
    resolve the unknown state, the branch still fell back to
    `self.cached_image`, which can be the exact pre-privacy frame this
    whole mechanism exists to protect. Must serve the placeholder instead.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = time.monotonic() - PRIVACY_UNKNOWN_RETRY_SEC
    assert CAM_ID not in entity.coordinator.shc_state_cache

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
        patch.object(entity, "_async_local_outage_snap", return_value=None),
    ):
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_fails_closed_on_racy_first_load_cache_fill(
    hass: HomeAssistant,
) -> None:
    """Tier 3 must also fail closed if the cache fills in mid-fetch.

    Regression test for a suppressed Copilot finding on PR #176545
    (2026-08-04, round 20): the first-load branch's own precondition is an
    empty/placeholder cache at entry, but `cached_image` can be concurrently
    set by `async_added_to_hass`'s disk restore while this branch's fetch is
    still awaiting — simulated here by having the mocked fetch itself write
    a real frame as a side effect before returning None. Tier 3 (the "cached
    image" fallback a few lines below) must not serve that frame while
    privacy is still unknown.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = entity._PLACEHOLDER_JPEG  # first-load branch precondition
    entity.last_image_fetch = time.monotonic() - 3600
    assert CAM_ID not in entity.coordinator.shc_state_cache

    async def _fetch_then_race_in_a_real_frame(*_a: object, **_kw: object) -> None:
        entity.cached_image = b"a-real-frame-that-raced-in-mid-fetch"

    with (
        patch.object(
            entity.coordinator,
            "async_fetch_live_snapshot",
            side_effect=_fetch_then_race_in_a_real_frame,
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
        patch.object(entity, "_async_local_outage_snap", return_value=None),
    ):
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_unknown_privacy_state_fails_closed_on_verification_timeout(
    hass: HomeAssistant,
) -> None:
    """Same fail-closed guarantee when the verification fetch times out.

    Regression test for the same round-20 Copilot finding, exercising the
    TimeoutError branch specifically rather than a clean REMOTE+LOCAL
    failure.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"a-real-cached-frame-from-before-privacy-was-enabled"
    entity.last_image_fetch = time.monotonic() - PRIVACY_UNKNOWN_RETRY_SEC
    assert CAM_ID not in entity.coordinator.shc_state_cache

    async def _hangs_forever(*_args: object, **_kwargs: object) -> bytes | None:
        await asyncio.sleep(10)
        return b"too-late"

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.camera.REFRESH_ON_STALE_CACHE_BUDGET_SEC",
            0.01,
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", side_effect=_hangs_forever
        ),
        patch.object(entity, "_async_local_outage_snap", return_value=None),
    ):
        image = await entity.async_camera_image()

    assert image == entity._PLACEHOLDER_JPEG


async def test_width_specific_fetch_does_not_poison_full_resolution_cache(
    hass: HomeAssistant,
) -> None:
    """A thumbnail (width=N) request must not overwrite the shared full-res cache."""
    entity = await _setup_camera_entity(hass)
    full_res_frame = b"full-resolution-frame"
    entity.cached_image = full_res_frame
    # Stale enough to enter the "cache stale" fetch-fresh branch.
    entity.last_image_fetch = time.monotonic() - 3600

    with patch.object(
        entity.coordinator,
        "async_fetch_live_snapshot",
        return_value=b"undersized-thumbnail",
    ):
        image = await entity.async_camera_image(width=200)

    assert image == b"undersized-thumbnail"
    # The shared cache must still hold the original full-resolution frame —
    # a subsequent full-res request must not be served the thumbnail.
    assert entity.cached_image == full_res_frame


async def test_failed_thumbnail_fetch_does_not_suppress_full_res_retry(
    hass: HomeAssistant,
) -> None:
    """A failed width=N (thumbnail) fetch must not advance the shared timestamp.

    Otherwise a following full-resolution request within the cache TTL
    would see `cache_stale=False` and skip retrying, even though the
    shared cache was never actually refreshed (Copilot review round 8).
    """
    entity = await _setup_camera_entity(hass)
    old_timestamp = time.monotonic() - 3600
    entity.last_image_fetch = old_timestamp  # stale enough to enter the fetch branch

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
        patch.object(
            entity.coordinator, "async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        await entity.async_camera_image(width=200)

    assert entity.last_image_fetch == old_timestamp


async def test_failed_thumbnail_fetch_with_real_cache_does_not_suppress_full_res_retry(
    hass: HomeAssistant,
) -> None:
    """Same guard as above, through the stale-but-already-cached branch.

    A real frame is already held, so both REMOTE+LOCAL failing must still
    not advance the shared timestamp for a width=N request.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"already-cached-full-res-frame"
    old_timestamp = time.monotonic() - 3600
    entity.last_image_fetch = old_timestamp  # stale

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
    ):
        await entity.async_camera_image(width=200)

    assert entity.last_image_fetch == old_timestamp


async def test_slow_refresh_falls_back_to_cached_image_within_budget(
    hass: HomeAssistant,
) -> None:
    """A REMOTE+LOCAL fetch chain slower than the internal budget falls back to the cached frame.

    Bounds the stale-cache refresh path well under HA-core's own
    CAMERA_IMAGE_TIMEOUT (10s) — without this, a slow/hanging cloud fetch
    would get the whole async_camera_image() call cancelled by HA core and
    serve nothing at all, instead of the frame we already have cached.
    """
    entity = await _setup_camera_entity(hass)
    cached_frame = b"last-known-good-frame"
    entity.cached_image = cached_frame
    entity.last_image_fetch = time.monotonic() - 3600  # stale
    # Known-safe privacy state — an unknown state would (correctly, per the
    # round-20 fail-closed fix) withhold this cached frame instead.
    entity.coordinator.shc_state_cache[CAM_ID] = {"privacy_mode": False}

    async def _hangs_forever(*_args: object, **_kwargs: object) -> bytes | None:
        await asyncio.sleep(10)
        return b"too-late"

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.camera.REFRESH_ON_STALE_CACHE_BUDGET_SEC",
            0.01,
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", side_effect=_hangs_forever
        ),
    ):
        image = await entity.async_camera_image()

    assert image == cached_frame


async def test_first_load_slow_refresh_falls_through_to_outage_snap_within_budget(
    hass: HomeAssistant,
) -> None:
    """The first-load branch's fetch is also bounded, not just the stale-cache one.

    Regression test for a suppressed Copilot finding on PR #176545
    (2026-08-04, round 20): unlike the stale-cache `elif` branch below it,
    the "first load" `if` branch had no internal timeout at all on its
    REMOTE+LOCAL fetch chain, so a hanging fetch here had no cutoff before
    HA-core's own CAMERA_IMAGE_TIMEOUT could cancel the whole call. Must
    fall through to the outage-snap tier within budget, same as the
    stale-cache branch.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = entity._PLACEHOLDER_JPEG  # no cache yet — first-load branch
    entity.last_image_fetch = (
        time.monotonic() - 3600
    )  # stale (boot sentinel equivalent)

    async def _hangs_forever(*_args: object, **_kwargs: object) -> bytes | None:
        await asyncio.sleep(10)
        return b"too-late"

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.camera.REFRESH_ON_STALE_CACHE_BUDGET_SEC",
            0.01,
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", side_effect=_hangs_forever
        ),
        patch.object(
            entity, "_async_local_outage_snap", return_value=b"local-outage-frame"
        ) as mock_outage,
    ):
        image = await entity.async_camera_image()

    mock_outage.assert_awaited_once()
    assert image == b"local-outage-frame"


async def test_stale_cache_both_fetches_fail_tries_local_outage_snap_first(
    hass: HomeAssistant,
) -> None:
    """A stale-cache double-fetch failure must try the LOCAL outage snap first.

    When REMOTE+LOCAL cloud fetches both fail on a stale cache, the LOCAL
    Digest-creds outage snap must be tried before falling back to the
    stale cached frame.

    A prior version only reached this fallback via the no-cache first-load
    path — every other failure point (this one included) returned the
    stale cached image directly, without ever trying it, even though the
    fallback's whole purpose is "the cloud/camera-API is unreachable"
    (Copilot review round 11). The gate on `coordinator.auth_outage_count`
    is also removed for the same reason: it only tracks OAuth/Keycloak
    token-refresh 5xx outages, not camera-cloud API failures, so it never
    reflected the actual condition this fallback exists to detect.
    """
    entity = await _setup_camera_entity(hass)
    entity.cached_image = b"stale-frame"
    entity.last_image_fetch = time.monotonic() - 3600  # stale
    entity.coordinator.auth_outage_count = 0  # deliberately 0 — must not gate
    entity.coordinator.local_creds_cache[CAM_ID] = {
        "user": "cbs-user",
        "password": "cbs-pass",
        "host": "192.168.1.50",
        "port": 443,
    }

    digest_resp = MagicMock()
    digest_resp.status = 200
    digest_resp.headers = {"Content-Type": "image/jpeg"}
    digest_resp.read = AsyncMock(return_value=b"\xff\xd8local-outage-frame")
    digest_cm = MagicMock()
    digest_cm.__aenter__ = AsyncMock(return_value=digest_resp)
    digest_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot", return_value=None
        ),
        patch.object(
            entity.coordinator, "async_fetch_live_snapshot_local", return_value=None
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.camera.async_digest_request",
            new=AsyncMock(return_value=digest_cm),
        ),
    ):
        image = await entity.async_camera_image()

    assert image == b"\xff\xd8local-outage-frame"
    assert entity.cached_image == b"\xff\xd8local-outage-frame"


async def test_unload_cancels_pending_image_refresh_task(hass: HomeAssistant) -> None:
    """Removing the entity mid-delay cancels its still-pending background refresh task.

    Without this, unloading during the startup/proactive refresh delay left a
    network task running against an already-removed entity (bug-hunt
    2026-07-27, Copilot review).
    """
    entity = await _setup_camera_entity(hass)

    # Simulate a still-pending background refresh (e.g. the 2s startup delay,
    # or a proactive-refresh trigger) scheduled but not yet complete.
    task = hass.async_create_task(entity.async_trigger_image_refresh(delay=100))
    entity._image_refresh_task = task
    await asyncio.sleep(0)  # let the task actually start (enter the sleep)

    await entity.async_will_remove_from_hass()
    await hass.async_block_till_done()

    assert task.cancelled()


async def test_coordinator_update_does_not_clobber_inflight_refresh_task(
    hass: HomeAssistant,
) -> None:
    """A coordinator update firing while a refresh is in flight must not clobber the tracked task.

    Must not replace the tracked task reference with a new (fast-exiting
    duplicate) one. `async_trigger_image_refresh` short-circuits a concurrent call via
    `_refresh_inflight` almost immediately — if `_handle_coordinator_update`
    unconditionally spawned a new task and overwrote `_image_refresh_task`
    with it, `async_will_remove_from_hass` would cancel that harmless
    duplicate instead of the real, still-running network task on entity
    removal (Copilot review round 7).
    """
    entity = await _setup_camera_entity(hass)
    entity.last_image_fetch = time.monotonic() - 3600  # stale enough to trigger

    real_task = hass.async_create_task(entity.async_trigger_image_refresh(delay=100))
    entity._image_refresh_task = real_task
    entity._refresh_inflight = True
    await asyncio.sleep(0)  # let the real task actually start

    entity._handle_coordinator_update()

    # No new task must have been spawned — the guard skips creation entirely
    # while `_refresh_inflight` is set, so the tracked reference is untouched.
    assert entity._image_refresh_task is real_task
    real_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await real_task


async def test_enable_motion_detection_raises_on_write_failure(
    hass: HomeAssistant,
) -> None:
    """A failed PUT must surface as HomeAssistantError, not silent success.

    `async_put_camera` returns False for HTTP/network/token-refresh
    failures — an ignored result made the camera service report success
    even though nothing changed (bug-hunt 2026-07-27, Copilot review
    round 3).
    """
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "async_put_camera", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_enable_motion_detection()


async def test_enable_motion_detection_updates_cache_on_success(
    hass: HomeAssistant,
) -> None:
    """A successful enable must update the cache + write-lock timestamp immediately.

    Motion is only re-fetched by the ~5-min slow tier, so without this
    `motion_detection_enabled` reads stale data for minutes (bug-hunt
    2026-07-27, Copilot review round 3).
    """
    entity = await _setup_camera_entity(hass)
    with patch.object(entity.coordinator, "async_put_camera", return_value=True):
        await entity.async_enable_motion_detection()

    assert entity.motion_detection_enabled is True
    assert CAM_ID in entity.coordinator.motion_set_at


async def test_enable_motion_detection_tracks_refresh_task(
    hass: HomeAssistant,
) -> None:
    """The post-enable refresh must go through `coordinator.spawn_tracked`.

    Not a bare `hass.async_create_task` — otherwise it can outlive
    config-entry unload and keep running against an already-torn-down
    coordinator (Copilot review round 12).
    """
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "async_put_camera", return_value=True),
        patch.object(entity.coordinator, "async_request_refresh", return_value=None),
        patch.object(
            entity.coordinator, "spawn_tracked", wraps=entity.coordinator.spawn_tracked
        ) as mock_spawn_tracked,
    ):
        await entity.async_enable_motion_detection()
    await hass.async_block_till_done()

    mock_spawn_tracked.assert_called_once()
    _, call_kwargs = mock_spawn_tracked.call_args
    assert call_kwargs["name"] == "bosch_shc_camera_motion_enable_refresh"


async def test_enable_motion_detection_raises_when_sensitivity_unknown(
    hass: HomeAssistant,
) -> None:
    """Must fail loudly, not invent a sensitivity, when motion settings haven't loaded yet.

    Silently defaulting to HIGH before the coordinator's slow tier has ever
    fetched motion settings (e.g. right after startup while the camera was
    offline) would reset a real LOW/MEDIUM setting the first time the
    coordinator's PUT actually lands (Copilot review round 13).
    """
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "motion_settings", return_value={}),
        patch.object(entity.coordinator, "async_put_camera") as mock_put,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_enable_motion_detection()
    mock_put.assert_not_called()


async def test_disable_motion_detection_raises_when_sensitivity_unknown(
    hass: HomeAssistant,
) -> None:
    """See test_enable_motion_detection_raises_when_sensitivity_unknown above."""
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "motion_settings", return_value={}),
        patch.object(entity.coordinator, "async_put_camera") as mock_put,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_disable_motion_detection()
    mock_put.assert_not_called()


async def test_disable_motion_detection_raises_on_write_failure(
    hass: HomeAssistant,
) -> None:
    """A failed disable PUT must surface as HomeAssistantError too."""
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "async_put_camera", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_disable_motion_detection()


async def test_disable_motion_detection_tracks_refresh_task(
    hass: HomeAssistant,
) -> None:
    """Same tracked-task guard as the enable path (Copilot review round 12)."""
    entity = await _setup_camera_entity(hass)
    with (
        patch.object(entity.coordinator, "async_put_camera", return_value=True),
        patch.object(entity.coordinator, "async_request_refresh", return_value=None),
        patch.object(
            entity.coordinator, "spawn_tracked", wraps=entity.coordinator.spawn_tracked
        ) as mock_spawn_tracked,
    ):
        await entity.async_disable_motion_detection()
    await hass.async_block_till_done()

    mock_spawn_tracked.assert_called_once()
    _, call_kwargs = mock_spawn_tracked.call_args
    assert call_kwargs["name"] == "bosch_shc_camera_motion_disable_refresh"
