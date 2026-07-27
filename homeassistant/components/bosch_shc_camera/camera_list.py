"""Camera list fetch + one 401→token-refresh→retry cycle.

Phase 2 step 2 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root) —
`BoschCameraCoordinator._async_update_data` (`__init__.py`) opens with a
`GET /v11/video_inputs` call whose result (`cam_list`) and possibly-mutated
`token`/`headers` feed every later section of the tick. Extracted second
(after the exception-handler dispatch in tick_failure.py) because it's
still self-contained — the only SYNCHRONOUS RETURN state it produces is
the three return values, threaded explicitly rather than via `self.`
mutation. It may also schedule a fire-and-forget outage-ping background
task as a side effect on a non-200 response — not captured in the return
tuple, unchanged from the pre-extraction inline code's behavior.

The `except UpdateFailed:`/`TimeoutError`/`aiohttp.ClientError` boundary
stays in `_async_update_data` itself — this function raises `UpdateFailed`
(or `ConfigEntryAuthFailed` when re-authentication is required) on failure
but does not catch anything; a raised timeout/network error here
propagates up through the SAME outer try/except in `__init__.py` as before
this extraction, unchanged.
"""

import asyncio
import json as _json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CLOUD_API, TIMEOUT_VIDEO_INPUTS, VIDEO_INPUTS_RETRY_DELAY_SEC

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
    a 401 here refreshes them in place. Raises `UpdateFailed` on a
    non-recoverable HTTP-status failure, or `ConfigEntryAuthFailed` when a
    freshly-renewed token is still rejected (re-authentication required).
    """
    # getattr handles stub coordinators in tests that predate the
    # diagnostic cloud_api_override field (real instances always set
    # self._cloud_api in __init__).
    cloud_api = getattr(coordinator, "_cloud_api", CLOUD_API)

    # One quick retry on a bare timeout (connect/read never completed within
    # TIMEOUT_VIDEO_INPUTS at all) before failing the whole tick over it —
    # see const.py's TIMEOUT_VIDEO_INPUTS docstring for the report that
    # prompted this. Does NOT apply to a real HTTP error status (401/5xx
    # etc.) — those are a definitive response, not a hiccup, and already
    # have their own defined handling below.
    for _attempt in range(2):
        try:
            async with asyncio.timeout(TIMEOUT_VIDEO_INPUTS):
                async with session.get(
                    f"{cloud_api}/v11/video_inputs", headers=headers
                ) as resp:
                    if resp.status == 401:
                        _LOGGER.info("Token expired (401) — attempting silent renewal")
                        _LOGGER.debug(
                            "video_inputs 401 body against %s (diagnostic, no "
                            "token material): %s",
                            cloud_api,
                            (await resp.text())[:300],
                        )
                        token = await coordinator.ensure_valid_token(token)
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/json",
                        }
                    elif resp.status != 200:
                        # Kick a LAN-ping sweep so the switch/light entities
                        # have a fresh reachability signal even though the
                        # cloud-driven status loop won't run this tick.
                        _outage_ping = getattr(
                            coordinator, "async_outage_ping_all", None
                        )
                        if _outage_ping is not None:
                            # Tracked (not a bare hass.async_create_task) —
                            # otherwise this can survive config-entry unload
                            # and keep running against a torn-down
                            # coordinator, bypassing the teardown contract
                            # the other outage-ping call sites already
                            # honor (Copilot review round 11).
                            coordinator.spawn_tracked(
                                _outage_ping(),
                                name="bosch_shc_camera_camera_list_outage_ping",
                            )
                        raise UpdateFailed(f"Camera list returned HTTP {resp.status}")
                    else:
                        cam_list = await resp.json()
            break
        except TimeoutError:
            if _attempt == 1:
                raise
            _LOGGER.debug(
                "video_inputs timed out against %s (attempt 1/2) — "
                "retrying once after %.0fs before failing the tick",
                cloud_api,
                VIDEO_INPUTS_RETRY_DELAY_SEC,
            )
            await asyncio.sleep(VIDEO_INPUTS_RETRY_DELAY_SEC)

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
                    # A genuinely renewed-then-still-rejected token means
                    # re-authentication is required — raise
                    # ConfigEntryAuthFailed so HA starts the native reauth
                    # flow automatically. UpdateFailed would just leave this
                    # non-transient condition retrying forever, and there is
                    # no manual "Force new browser login" options-flow
                    # control in this build to direct the user to (bug-hunt
                    # 2026-07-27, Copilot review round 3).
                    raise ConfigEntryAuthFailed(
                        "Token expired and renewal failed — re-authentication required"
                    )
                if resp2.status != 200:
                    raise UpdateFailed(f"Camera list returned HTTP {resp2.status}")
                cam_list = await resp2.json()

    return cam_list, token, headers
