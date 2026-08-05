"""LOCAL-only RTSP stream wiring for the camera platform.

Opens a Bosch LOCAL session (`PUT /v11/video_inputs/{id}/connection`,
type=LOCAL) to obtain per-session Digest credentials and the camera's LAN
address, then runs a TCP→TLS proxy
(`bosch_shc_camera_client.tls_proxy`) so HA's stream component — which
cannot speak RTSPS against a self-signed certificate — can consume a plain
`rtsp://` URL instead.

This integration is snapshot-first: unlike the sibling HACS project, there
is no credential-rotation renewal and no REMOTE/cloud-relay fallback here.
If the proxy's own circuit breaker trips (the camera stops responding), the
caller is notified via `on_proxy_died` and the entity simply reports no
stream source until the integration is reloaded.
"""

import asyncio
from collections.abc import Callable
import json
import logging
import ssl
from typing import TYPE_CHECKING
from urllib.parse import quote

import aiohttp
from bosch_shc_camera_client.tls_proxy import start_tls_proxy, stop_tls_proxy

from .cloud_ssl import async_bosch_cloud_session_cm
from .const import (
    CLOUD_API,
    LOCAL_STREAM_MAX_SESSION_DURATION_SEC,
    TIMEOUT_PUT_CONNECTION,
)
from .coordinator import _is_safe_local_camera_host

if TYPE_CHECKING:
    from .coordinator import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


def _build_local_stream_ssl_context() -> ssl.SSLContext:
    """Build the TLS context for the LOCAL proxy. Blocking — run in executor.

    The camera presents a self-signed certificate on its LAN address, so
    verification must be disabled: the trust anchor for this session is the
    Digest credentials Bosch's cloud API just issued, not the TLS
    certificate.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def async_start_local_stream(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    port_cache: dict[str, int],
    server_cache: dict[str, asyncio.base_events.Server],
    on_proxy_died: Callable[[], None] | None = None,
) -> str | None:
    """Open a LOCAL session for `cam_id` and start its TLS proxy.

    Returns a credential-embedded `rtsp://127.0.0.1:<port>/rtsp_tunnel...`
    URL for HA's stream component, or None if the camera is unreachable, the
    session could not be established, or the returned host looked unsafe.
    """
    token = coordinator.token
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    high_quality, inst = coordinator.get_quality_params(cam_id)

    try:
        async with async_bosch_cloud_session_cm(coordinator.hass) as session:
            async with asyncio.timeout(TIMEOUT_PUT_CONNECTION):
                async with session.put(
                    f"{CLOUD_API}/v11/video_inputs/{cam_id}/connection",
                    json={"type": "LOCAL", "highQualityVideo": high_quality},
                    headers=headers,
                ) as resp:
                    if resp.status not in (200, 201):
                        _LOGGER.debug(
                            "LOCAL stream: PUT /connection -> HTTP %d for %s",
                            resp.status,
                            cam_id,
                        )
                        return None
                    result = json.loads(await resp.text())
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.debug("LOCAL stream: PUT /connection error for %s: %s", cam_id, err)
        return None

    user = result.get("user")
    password = result.get("password")
    urls = result.get("urls", [])
    if not user or not password or not urls:
        _LOGGER.debug(
            "LOCAL stream: missing credentials/urls for %s (has_user=%s, "
            "has_password=%s, urls=%d)",
            cam_id,
            bool(user),
            bool(password),
            len(urls),
        )
        return None

    cam_addr = urls[0]  # e.g. "192.168.x.x:443"
    if not _is_safe_local_camera_host(cam_addr):
        _LOGGER.warning(
            "LOCAL stream: rejected unsafe/malformed camera host for %s: %s",
            cam_id,
            cam_addr[:60],
        )
        return None
    cam_host, _, cam_port_str = cam_addr.partition(":")

    ssl_ctx = await coordinator.hass.async_add_executor_job(
        _build_local_stream_ssl_context
    )
    proxy_port = await start_tls_proxy(
        ssl_ctx,
        cam_id,
        cam_host,
        int(cam_port_str),
        port_cache,
        server_cache,
        on_proxy_died=on_proxy_died,
    )

    escaped_user = quote(user, safe="")
    escaped_password = quote(password, safe="")
    return (
        f"rtsp://{escaped_user}:{escaped_password}@127.0.0.1:{proxy_port}"
        f"/rtsp_tunnel?inst={inst}&enableaudio=1&fmtp=1"
        f"&maxSessionDuration={LOCAL_STREAM_MAX_SESSION_DURATION_SEC}"
    )


async def async_stop_local_stream(
    cam_id: str,
    port_cache: dict[str, int],
    server_cache: dict[str, asyncio.base_events.Server],
) -> None:
    """Stop this camera's TLS proxy, if one is running."""
    await stop_tls_proxy(cam_id, port_cache, server_cache)
