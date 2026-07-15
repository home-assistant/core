"""Camera list fetch + one 401→token-refresh→retry cycle.

Phase 2 step 2 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root) —
`BoschCameraCoordinator._async_update_data` (`__init__.py`) opens with a
`GET /v11/video_inputs` call whose result (`cam_list`) and possibly-mutated
`token`/`headers` feed every later section of the tick. Extracted second
(after the exception-handler dispatch in tick_failure.py) because it's
still self-contained — the only SYNCHRONOUS RETURN state it produces is
the three return values, threaded explicitly rather than via `self.`
mutation. It may also schedule fire-and-forget background tasks as a side
effect (maintenance-refresh/outage-ping on a non-200 response) — those are
not captured in the return tuple, unchanged from the pre-extraction inline
code's behavior.

The `except UpdateFailed:`/`TimeoutError`/`aiohttp.ClientError` boundary
stays in `_async_update_data` itself — this function raises `UpdateFailed`
on failure but does not catch anything; a raised timeout/network error
here propagates up through the SAME outer try/except in `__init__.py` as
before this extraction, unchanged.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CLOUD_API

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def fetch_camera_list(
    coordinator: BoschCameraCoordinator,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    token: str,
) -> tuple[list[Any], str, dict[str, str]]:
    """Fetch the camera list, handling one 401→token-refresh→retry cycle.

    Returns ``(cam_list, token, headers)`` — the caller must use the
    returned `token`/`headers` for every subsequent request this tick, since
    a 401 here refreshes them in place. Raises `UpdateFailed` on any
    non-recoverable failure (non-200/401 status, or the retry also 401s).
    """
    # getattr handles stub coordinators in tests that predate the
    # diagnostic cloud_api_override field (real instances always set
    # self._cloud_api in __init__).
    cloud_api = getattr(coordinator, "_cloud_api", CLOUD_API)

    async with asyncio.timeout(15):
        async with session.get(
            f"{cloud_api}/v11/video_inputs", headers=headers
        ) as resp:
            if resp.status == 401:
                _LOGGER.info("Token expired (401) — attempting silent renewal")
                _LOGGER.debug(
                    "video_inputs 401 body against %s (diagnostic, no token "
                    "material): %s",
                    cloud_api,
                    (await resp.text())[:300],
                )
                token = await coordinator.ensure_valid_token(token)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
            elif resp.status != 200:
                # Cloud 5xx often coincides with announced maintenance —
                # kick off a background fetch of the community RSS so
                # the UI can show a specific reason instead of generic
                # "unavailable". Rate-limited inside the helper.
                # getattr handles stub coordinators in tests.
                _maint = getattr(coordinator, "_async_refresh_maintenance", None)
                if _maint is not None:
                    coordinator.hass.async_create_task(_maint(reactive=True))
                # And kick a LAN-ping sweep so the switch/light entities
                # have a fresh reachability signal even though the
                # cloud-driven status loop won't run this tick.
                _outage_ping = getattr(coordinator, "async_outage_ping_all", None)
                if _outage_ping is not None:
                    coordinator.hass.async_create_task(_outage_ping())
                raise UpdateFailed(f"Camera list returned HTTP {resp.status}")
            else:
                cam_list = await resp.json()

    # Retry after renewal if we got a 401
    if resp.status == 401:
        async with asyncio.timeout(15):
            async with session.get(
                f"{cloud_api}/v11/video_inputs", headers=headers
            ) as resp2:
                if resp2.status == 401:
                    body_text = (await resp2.text())[:300]
                    _LOGGER.debug(
                        "video_inputs retry still 401 after renewal against "
                        "%s — Bosch response body (diagnostic, no token "
                        "material): %s",
                        cloud_api,
                        body_text,
                    )
                    try:
                        body_json = _json.loads(body_text)
                    except ValueError:
                        body_json = {}
                    # A fresh, successfully-renewed token still being 401'd
                    # is not a token problem at all — Bosch is telling us
                    # the account itself lacks camera-API access (e.g. a
                    # shared-user registration that never completed).
                    # Re-authenticating cannot fix this; say so instead of
                    # sending the user in an endless, pointless relogin loop
                    # (2026-07-06 SebastianHarder community report — debug
                    # logging above finally surfaced the real reason).
                    if body_json.get("error") == "sh:authorization.failed":
                        # The official Bosch Camera App performs a separate,
                        # one-time "registration/check" step against the camera
                        # backend after SingleKey ID login (name/marketing-consent/
                        # T&C acceptance, distinct from login itself) — an account
                        # that never went through that screen (e.g. reached camera
                        # access via a beta/invite path rather than the normal
                        # in-app first run) gets a permanently valid login but a
                        # permanently rejected camera-API token. Re-authenticating
                        # only repeats the login step, so it cannot fix this.
                        raise UpdateFailed(
                            "Bosch rejected the camera API with "
                            f"'sh:authorization.failed' ({body_json.get('message', 'no detail')}) "
                            "— this is an account/permission issue on Bosch's side, not a "
                            "login problem. Re-authenticating will not fix it. Open the "
                            "official Bosch Smart Camera App and complete any registration "
                            "or terms-of-service screen it shows on next login — this "
                            "integration only logs in and does not perform that separate "
                            "camera-account registration step. If no such screen appears, "
                            "contact Bosch support."
                        )
                    raise UpdateFailed(
                        "Token expired and renewal failed — go to Settings → Integrations → "
                        "Bosch Smart Home Camera → Configure → Force new browser login"
                    )
                if resp2.status != 200:
                    raise UpdateFailed(f"Camera list returned HTTP {resp2.status}")
                cam_list = await resp2.json()

    return cam_list, token, headers
