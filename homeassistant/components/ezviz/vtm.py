"""Serve EZVIZ live video from pyezvizapi as MPEG-TS over the local HA HTTP server.

Many EZVIZ devices (battery cameras, doorbells, newer firmware) no longer expose
RTSP. pyezvizapi streams them through the EZVIZ cloud as ready MPEG-TS; this
module only exposes that stream on a local URL that the camera entity returns
as its stream source.

Each camera URL carries its own random access token instead of HA auth, because
the consumers (the stream worker and go2rtc) cannot send HA credentials. The
token is passed as the ``auth`` query parameter, which the stream integration
redacts from its logs. Unloading the config entry drops the token and ends the
streams that are still running.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
import hmac
import logging
import secrets

from aiohttp import web
from pyezvizapi.client import EzvizClient
from pyezvizapi.exceptions import PyEzvizError
from pyezvizapi.streaming.capture import AutoClipSource
from pyezvizapi.streaming.live import (
    LiveMpegtsStream,
    LiveStreamShutdownTimeout,
    open_live_mpegts_stream,
)

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

VTM_URL = "/api/ezviz/vtm/{serial}.ts"
READ_CHUNK = 65536
# Battery devices need about 10 s to wake up before the first media arrives.
STARTUP_TIMEOUT = 30.0
# The library asks callers to retry close() after a shutdown timeout.
CLOSE_ATTEMPTS = 3


@dataclass
class VtmCamera:
    """A camera reachable through the live stream view."""

    client: EzvizClient
    access_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    # Request handler tasks currently streaming this camera.
    streams: set[asyncio.Task] = field(default_factory=set)


DATA_VTM: HassKey[dict[str, VtmCamera]] = HassKey(f"{DOMAIN}_vtm")


@callback
def async_register_vtm_camera(
    hass: HomeAssistant, entry: ConfigEntry, serial: str, client: EzvizClient
) -> None:
    """Make a camera streamable until its config entry unloads."""
    if (cameras := hass.data.get(DATA_VTM)) is None:
        cameras = hass.data[DATA_VTM] = {}
        hass.http.register_view(EzvizVtmStreamView())
    camera = cameras[serial] = VtmCamera(client)

    @callback
    def _unregister() -> None:
        if cameras.get(serial) is camera:
            del cameras[serial]
        for task in camera.streams:
            task.cancel()

    entry.async_on_unload(_unregister)


def vtm_stream_url(hass: HomeAssistant, serial: str) -> str | None:
    """Return the internal URL serving the live stream of a camera.

    The consumer may be go2rtc on another host, so use the configured internal
    URL rather than loopback.
    """
    if (camera := hass.data.get(DATA_VTM, {}).get(serial)) is None:
        return None
    try:
        base_url = get_url(
            hass,
            allow_external=False,
            allow_cloud=False,
            allow_ip=True,
            prefer_external=False,
        )
    except NoURLAvailableError:
        return None
    path = VTM_URL.format(serial=serial)
    return f"{base_url}{path}?auth={camera.access_token}"


class EzvizVtmStreamView(HomeAssistantView):
    """Stream one camera's live MPEG-TS from pyezvizapi."""

    url = VTM_URL
    name = "api:ezviz:vtm"
    requires_auth = False

    async def get(self, request: web.Request, serial: str) -> web.StreamResponse:
        """Copy the live stream to the HTTP client until either side ends."""
        hass = request.app[KEY_HASS]
        camera = hass.data.get(DATA_VTM, {}).get(serial)
        access_token = request.query.get("auth", "")
        # Compare bytes: compare_digest rejects non-ASCII str input with TypeError.
        if camera is None or not hmac.compare_digest(
            access_token.encode(), camera.access_token.encode()
        ):
            raise web.HTTPNotFound

        # Track the handler before the first await, so unloading the entry at
        # any point after authentication cancels it.
        task = asyncio.current_task()
        if task is not None:
            camera.streams.add(task)
        try:
            return await _async_stream(hass, request, camera, serial)
        finally:
            if task is not None:
                camera.streams.discard(task)


async def _async_stream(
    hass: HomeAssistant, request: web.Request, camera: VtmCamera, serial: str
) -> web.StreamResponse:
    """Open the live stream and write it to the HTTP response."""
    # Reads block for as long as the viewer watches, so they get their own
    # threads instead of the shared executor. The second thread stays free for
    # close(), which interrupts a blocked read.
    executor = ThreadPoolExecutor(
        max_workers=2, thread_name_prefix=f"ezviz_live_{serial}"
    )
    loop = asyncio.get_running_loop()
    try:
        opening = loop.run_in_executor(
            executor,
            partial(
                open_live_mpegts_stream,
                camera.client,
                serial,
                ffmpeg_path=get_ffmpeg_manager(hass).binary,
                source=AutoClipSource(mode="cloud", timeout=STARTUP_TIMEOUT),
            ),
        )
        stream = await asyncio.shield(opening)
    except asyncio.CancelledError:
        # Cancelled while opening: close the stream once the open finishes.
        opening.add_done_callback(partial(_close_opened_stream, executor, serial))
        raise
    except PyEzvizError as err:
        executor.shutdown(wait=False)
        _LOGGER.warning("%s: cannot open live stream: %s", serial, err)
        raise web.HTTPServiceUnavailable from err

    response = web.StreamResponse(
        headers={"Content-Type": "video/MP2T", "Cache-Control": "no-store"}
    )
    _LOGGER.debug("%s: live stream opened", serial)
    try:
        await response.prepare(request)
        while chunk := await loop.run_in_executor(executor, stream.read, READ_CHUNK):
            await response.write(chunk)
    except ConnectionResetError:
        pass
    except PyEzvizError as err:
        _LOGGER.warning("%s: live stream failed: %s", serial, err)
    finally:
        # Queue close() before shutting the executor down; queued work still
        # runs, and the shield keeps a second cancellation from dropping it.
        closing = loop.run_in_executor(executor, _close_stream, stream, serial)
        executor.shutdown(wait=False)
        await asyncio.shield(closing)
        _LOGGER.debug("%s: live stream closed", serial)
    return response


def _close_opened_stream(
    executor: ThreadPoolExecutor,
    serial: str,
    opening: asyncio.Future[LiveMpegtsStream],
) -> None:
    """Close a stream whose request was cancelled while it was opening."""
    if not opening.cancelled() and opening.exception() is None:
        executor.submit(_close_stream, opening.result(), serial)
    executor.shutdown(wait=False)


def _close_stream(stream: LiveMpegtsStream, serial: str) -> None:
    """Close the stream, retrying while the library reports a shutdown timeout."""
    for _ in range(CLOSE_ATTEMPTS):
        try:
            stream.close()
        except LiveStreamShutdownTimeout:
            continue
        except PyEzvizError as err:
            _LOGGER.warning("%s: live stream cleanup failed: %s", serial, err)
        return
    _LOGGER.warning(
        "%s: live stream did not shut down after %s attempts", serial, CLOSE_ATTEMPTS
    )
