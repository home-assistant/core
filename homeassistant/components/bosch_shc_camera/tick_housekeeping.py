"""Post-tick housekeeping: stale-device pruning, availability-transition notify.

Also covers LAN-IP/hw-version/local-creds persistence and cloud-state notify.

Phase 2 step 6 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Everything
here is fire-and-forget (`hass.async_create_task`/
`async_create_background_task`) or a cheap in-memory check — none of
it blocks the coordinator tick's return of `data`. Deliberately does
NOT include `_refresh_notifications_disabled_issues`/
`_refresh_firmware_update_issues` — those stay as their own coordinator
methods called directly from `_async_update_data`, per the orchestrator
skeleton in the plan file.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def run_housekeeping(
    coordinator: BoschCameraCoordinator,
    data: dict[str, Any],
    opts: dict[str, Any],
    now: float,
    is_first_tick: bool,
) -> None:
    """Run the post-tick housekeeping pass. Mutates coordinator state only."""
    # Quality-Scale Gold (stale-devices): remove devices for cameras that
    # no longer exist in the Bosch cloud account. Skip on the fast first
    # tick so we don't race the device-registry creation in async_setup_entry.
    # `data` is only ever a genuine, successful fetch result by this point —
    # fetch_camera_list raises on any failure before reaching here — so an
    # empty `data` is a definitive zero-camera account, not a fetch glitch,
    # and must still run cleanup (an `and data` guard here previously left
    # the account's last-removed camera's device/state behind forever;
    # bug-hunt 2026-07-27, Copilot review round 3).
    if not is_first_tick:
        coordinator.cleanup_stale_devices(set(data.keys()))

    # Per-camera availability transition notifier — fires when a cam
    # flips between online and offline. First tick is silent (records
    # baseline). Skipped on the fast first tick because the cache is
    # still being populated and could carry a stale "online" from a
    # restore_state load. Defensive getattr handles stub coordinators
    # in unit tests that bypass __init__ (~80 fixtures across the
    # test suite).
    _announce = getattr(coordinator, "_async_maybe_announce_camera_status", None)
    _compute = getattr(coordinator, "_compute_status_for", None)
    if not is_first_tick and data and _announce is not None and _compute is not None:
        for _cam_id, _cam_data in data.items():
            new_status = _compute(_cam_id, _cam_data)
            coordinator.spawn_tracked(
                _announce(_cam_id, new_status),
                name=f"bosch_shc_camera_status_announce_{_cam_id[:8]}",
            )

    # Persist LAN IPs (cam_id → IP) so the next cloud-degraded
    # startup can ping cameras without first needing a cloud call.
    # Throttle: only write if the mapping actually changed.
    _store = getattr(coordinator, "lan_ips_store", None)
    if _store is not None:
        _snapshot = {k: v for k, v in coordinator.rcp_lan_ip_cache.items() if v}
        _prev = getattr(coordinator, "lan_ips_snapshot", None)
        # No truthiness guard on `_snapshot` here — cleanup_stale_devices()
        # clears rcp_lan_ip_cache when the account's last camera is removed,
        # and that empty snapshot must still be persisted, or the stale
        # camera ID/IP is reloaded and pinged again after a restart
        # (bug-hunt 2026-07-27, Copilot review round 5 — same class of bug
        # already fixed for local_creds_cache in round 3).
        if _snapshot != _prev:
            coordinator.lan_ips_snapshot = _snapshot
            coordinator.spawn_tracked(
                _store.async_save(_snapshot), name="bosch_shc_camera_lan_ips_save"
            )

    # Persist hardware versions (cam_id → hw_version) for the same
    # cloud-degraded-startup reason — without this, _is_gen2() defaults
    # to Gen1 after a cold start during a cloud outage, which makes
    # the LAN-fallback gate on the privacy / front-light switches
    # report "unavailable" even though the LAN RCP path would work.
    _hw_store = getattr(coordinator, "hw_version_store", None)
    if _hw_store is not None and coordinator.hw_version:
        _hw_snapshot = {k: v for k, v in coordinator.hw_version.items() if v}
        _hw_prev = getattr(coordinator, "hw_version_snapshot", None)
        if _hw_snapshot and _hw_snapshot != _hw_prev:
            coordinator.hw_version_snapshot = _hw_snapshot
            coordinator.spawn_tracked(
                _hw_store.async_save(_hw_snapshot),
                name="bosch_shc_camera_hw_version_save",
            )

    # Persist LOCAL Digest creds so LAN-fallback privacy / light
    # writes survive HA restarts during a Bosch cloud outage. Without
    # this, every cold restart while the cloud is 503 leaves the cred
    # cache empty and the LAN RCP write returns <err> "no auth".
    _creds_store = getattr(coordinator, "local_creds_store", None)
    if _creds_store is not None:
        _cred_snapshot = {
            k: {
                "user": v["user"],
                "password": v["password"],
                "host": v["host"],
                "port": v.get("port", 443),
            }
            for k, v in coordinator.local_creds_cache.items()
            if v.get("user") and v.get("password") and v.get("host")
        }
        _cred_prev = getattr(coordinator, "local_creds_snapshot", None)
        # No truthiness guard on `_cred_snapshot` here — the account's last
        # camera being removed clears `local_creds_cache` to `{}`, and that
        # empty snapshot must still be persisted so the deleted camera's
        # Digest credentials don't remain in `.storage` indefinitely
        # (bug-hunt 2026-07-27, Copilot review round 3).
        if _cred_snapshot != _cred_prev:
            coordinator.local_creds_snapshot = _cred_snapshot
            coordinator.spawn_tracked(
                _creds_store.async_save(_cred_snapshot),
                name="bosch_shc_camera_local_creds_save",
            )

    # Cloud-state transition notifier (v12.4.11). Called directly
    # (awaited) rather than spawned as a task: this call site always
    # passes success=True, and `_async_maybe_announce_cloud_state`
    # early-returns immediately (a couple of in-memory attribute
    # checks, no I/O) unless a prior outage was actually announced —
    # the rare "recovery" branch it can fall into only fires
    # `hass.services.async_call(..., blocking=False)`, which schedules
    # the notify service without waiting for it to finish, so it's
    # cheap too. Spawning a fresh `async_create_task` every tick for a
    # call that almost always no-ops was pure overhead (perf-refactor
    # Phase 1 step 5). getattr handles stub coordinators in tests that
    # bypass __init__.
    _cloud_alert = getattr(coordinator, "_async_maybe_announce_cloud_state", None)
    if _cloud_alert is not None:
        await _cloud_alert(True)
