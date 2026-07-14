"""One-time bootstrap fetches inside `_async_update_data`.

Phase 2 step 3 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Feature-flags and
the Bosch API protocol-version check are each guarded by an instance flag
(`self._feature_flags`/`self._protocol_checked`) so they only genuinely run
on the first tick, but the guard checks themselves are re-evaluated every
tick inline — this is bootstrap-shaped logic riding along in the per-tick
polling method, not repeated polling work. Left inline-called on every tick
(not moved to a scheduled background task) per the plan's own judgment
call: the existing throttle guards ARE the correctness mechanism, and
converting to `async_track_time_interval` would change failure/ordering
semantics for no benefit at this stage.

Both functions swallow their own failures (matching the pre-extraction
inline code exactly) — a fetch failure here must never abort the tick,
since the outer `_async_update_data` try/except boundary is reserved for
genuine camera-list/status/events failures.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp

from .const import CLOUD_API

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def ensure_feature_flags(
    coordinator: BoschCameraCoordinator,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> None:
    """Fetch `/v11/feature_flags` once, caching onto `coordinator._feature_flags`.

    No-op once `coordinator._feature_flags` is already truthy. Any timeout/
    network error is swallowed (debug-logged) — a missing feature-flags
    fetch must not abort the tick.
    """
    if coordinator._feature_flags:
        return
    try:
        async with asyncio.timeout(5):
            async with session.get(
                f"{CLOUD_API}/v11/feature_flags", headers=headers
            ) as ff_resp:
                if ff_resp.status == 200:
                    coordinator._feature_flags = await ff_resp.json()
                    _LOGGER.debug("Feature flags: %s", coordinator._feature_flags)
    except asyncio.CancelledError:
        raise
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.debug("Feature flags fetch failed: %s", err)


async def ensure_protocol_checked(
    coordinator: BoschCameraCoordinator,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> None:
    """Check the Bosch API protocol version once, at startup.

    No-op once `coordinator._protocol_checked` is already `True` — that
    flag is set unconditionally the first time this runs (before the fetch
    even completes), matching the pre-extraction inline code exactly:
    a failed check must not retry every tick. Logs a WARNING if the
    protocol is no longer reported as SUPPORTED, or if the check itself
    fails — never raises.
    """
    if coordinator._protocol_checked:
        return
    coordinator._protocol_checked = True
    try:
        _version = coordinator._integration_version
        async with asyncio.timeout(5):
            async with session.get(
                f"{CLOUD_API}/protocol_support?protocol=11&client=haV{_version}",
                headers=headers,
            ) as proto_resp:
                if proto_resp.status == 200:
                    proto_data = await proto_resp.json()
                    if proto_data.get("state") != "SUPPORTED":
                        _LOGGER.warning(
                            "Bosch API protocol version 11 may no longer be supported "
                            "(state=%s) — consider updating the integration",
                            proto_data.get("state"),
                        )
                    else:
                        _LOGGER.debug("Protocol v11 supported: %s", proto_data)
                else:
                    _LOGGER.warning(
                        "Bosch API protocol version check returned HTTP %s "
                        "— consider updating the integration",
                        proto_resp.status,
                    )
    except Exception as exc:
        _LOGGER.debug("Protocol version check failed: %s", exc)
