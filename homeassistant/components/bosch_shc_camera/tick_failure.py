"""Side effects for `_async_update_data`'s outer exception handlers.

First extraction of the Phase 2 coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, in the project root) —
`BoschCameraCoordinator._async_update_data` (`__init__.py`) is ~1500 lines
covering the whole per-tick polling cycle; this module owns only the
three `except` branches at its tail. Chosen to extract FIRST because it has
no cross-section local-variable threading — each function is a pure side
effect dispatch keyed off which exception fired, called from `__init__.py`'s
own `try`/`except` (the try/except boundary itself stays in
`_async_update_data`, not here — moving it would change the "any unhandled
error anywhere aborts the whole tick" contract the whole method depends on).

Every dispatch function reproduces the exact `getattr(..., None)` guard the
original inline code used (defensive against stub coordinators in tests
that don't define every announce/notify method) and the exact task-creation
order — no reordering, no new side effects.
"""

import logging
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.helpers.update_coordinator import UpdateFailed

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def dispatch_update_failed(coordinator: BoschCameraCoordinator) -> None:
    """Side effect for `except UpdateFailed:` — caller still re-raises."""
    _cloud_alert = getattr(coordinator, "_async_maybe_announce_cloud_state", None)
    if _cloud_alert is not None:
        coordinator.spawn_tracked(
            _cloud_alert(False), name="bosch_shc_camera_cloud_alert_update_failed"
        )


async def dispatch_timeout(coordinator: BoschCameraCoordinator) -> UpdateFailed:
    """Run side effects for `except TimeoutError:`.

    Returns the `UpdateFailed` the caller must `raise ... from None`.
    """
    _maint = getattr(coordinator, "_async_refresh_maintenance", None)
    if _maint is not None:
        coordinator.spawn_tracked(
            _maint(reactive=True), name="bosch_shc_camera_maint_refresh_timeout"
        )
    _outage_ping = getattr(coordinator, "async_outage_ping_all", None)
    if _outage_ping is not None:
        coordinator.spawn_tracked(
            _outage_ping(), name="bosch_shc_camera_outage_ping_timeout"
        )
    _cloud_alert = getattr(coordinator, "_async_maybe_announce_cloud_state", None)
    if _cloud_alert is not None:
        coordinator.spawn_tracked(
            _cloud_alert(False), name="bosch_shc_camera_cloud_alert_timeout"
        )
    return UpdateFailed("Timeout fetching camera data from Bosch cloud")


async def dispatch_client_error(
    coordinator: BoschCameraCoordinator, err: aiohttp.ClientError
) -> UpdateFailed:
    """Run side effects for `except aiohttp.ClientError as err:`.

    Returns the `UpdateFailed` the caller must `raise ... from err`.
    """
    _cloud_alert = getattr(coordinator, "_async_maybe_announce_cloud_state", None)
    if _cloud_alert is not None:
        coordinator.spawn_tracked(
            _cloud_alert(False), name="bosch_shc_camera_cloud_alert_client_error"
        )
    return UpdateFailed(f"Network error: {err}")
