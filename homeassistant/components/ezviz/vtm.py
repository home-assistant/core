"""Serve the EZVIZ VTM cloud relay stream as MPEG-TS over the local HA HTTP server.

Many EZVIZ devices (battery cameras, doorbells, newer firmware) no longer expose
RTSP. The EZVIZ apps still show live video through the VTM cloud relay, which
delivers MPEG-PS over TCP. This module opens that relay with pyezvizapi, remuxes
it to MPEG-TS with FFmpeg (codec copy, no transcoding) and serves it on a local
URL that the camera entity returns as its stream source.

Each camera URL carries its own random access token instead of HA auth, because
the consumers (the stream worker and go2rtc) cannot send HA credentials. The
token is passed as the ``auth`` query parameter, which the stream integration
redacts from its logs. Unloading the config entry drops the token and ends the
streams that are still running.
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import hmac
import logging
import secrets
import socket
import threading

from aiohttp import web
from pyezvizapi.client import EzvizClient
from pyezvizapi.cloud_stream import open_cloud_stream
from pyezvizapi.exceptions import PyEzvizError

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
# Relay packets are about 1.4 kB, so this caps the backlog at roughly 360 kB.
QUEUE_SIZE = 256
QUEUE_PUT_TIMEOUT = 1.0
RELAY_JOIN_TIMEOUT = 5.0


@dataclass
class VtmCamera:
    """A camera reachable through the VTM stream view."""

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
    """Return the internal URL serving the VTM stream of a camera.

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


def rtsp_available(camera_data: dict) -> bool:
    """Return False when the cloud reports the device has no local RTSP server.

    pyezvizapi falls back to 554 for ``local_rtsp_port``, so check the raw
    CONNECTION block, where devices without RTSP report ``localRtspPort: 0``.
    """
    connection = camera_data.get("CONNECTION")
    if not isinstance(connection, dict) or "localRtspPort" not in connection:
        return True
    return bool(connection["localRtspPort"])


class EzvizVtmStreamView(HomeAssistantView):
    """Stream one camera's VTM relay as MPEG-TS."""

    url = VTM_URL
    name = "api:ezviz:vtm"
    requires_auth = False

    async def get(self, request: web.Request, serial: str) -> web.StreamResponse:
        """Open the relay and copy it to the HTTP client until it disconnects."""
        hass = request.app[KEY_HASS]
        camera = hass.data.get(DATA_VTM, {}).get(serial)
        access_token = request.query.get("auth", "")
        if camera is None or not hmac.compare_digest(access_token, camera.access_token):
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
    """Remux the camera relay through FFmpeg into the HTTP response."""
    process = await asyncio.create_subprocess_exec(
        get_ffmpeg_manager(hass).binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "mpeg",
        "-i",
        "pipe:0",
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "mpegts",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdin = process.stdin
        stdout = process.stdout
        if stdin is None or stdout is None:  # pragma: no cover - PIPE requested
            raise web.HTTPInternalServerError

        queue: asyncio.Queue[bytes | None] = asyncio.Queue(QUEUE_SIZE)
        relay = VtmRelay(camera.client, serial, asyncio.get_running_loop(), queue)
        relay.start()
        feeder = asyncio.create_task(_feed_ffmpeg(queue, stdin))
        _LOGGER.debug("%s: VTM stream opened", serial)
        try:
            response = web.StreamResponse(
                headers={"Content-Type": "video/MP2T", "Cache-Control": "no-store"}
            )
            await response.prepare(request)
            while chunk := await stdout.read(READ_CHUNK):
                await response.write(chunk)
        except ConnectionResetError:
            pass
        finally:
            relay.stop()
            feeder.cancel()
            await _async_stop_process(process)
            await hass.async_add_executor_job(relay.join, RELAY_JOIN_TIMEOUT)
            _LOGGER.debug("%s: VTM stream closed", serial)
    finally:
        await _async_stop_process(process)
    return response


async def _async_stop_process(process: asyncio.subprocess.Process) -> None:
    """Kill FFmpeg if it is still running and reap it."""
    if process.returncode is None:
        with suppress(ProcessLookupError):
            # FFmpeg may have exited between the check and the kill.
            process.kill()
    await process.wait()


class VtmRelay:
    """Read the VTM relay in a worker thread and hand payloads to the loop.

    The pyezvizapi VTM client uses blocking sockets, so it runs in its own
    thread instead of holding an executor worker for the whole session. The
    bounded queue blocks the thread when FFmpeg or the HTTP client fall behind.
    """

    def __init__(
        self,
        client: EzvizClient,
        serial: str,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[bytes | None],
    ) -> None:
        """Initialize the relay reader."""
        self._client = client
        self._serial = serial
        self._loop = loop
        self._queue = queue
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._sockets: list[socket.socket] = []
        self._thread = threading.Thread(
            target=self._run, name=f"ezviz_vtm_{serial}", daemon=True
        )

    def start(self) -> None:
        """Start reading the relay."""
        self._thread.start()

    def stop(self) -> None:
        """Stop reading and unblock a pending socket read."""
        self._stop.set()
        with self._lock:
            for sock in self._sockets:
                with suppress(OSError):
                    sock.shutdown(socket.SHUT_RDWR)

    def join(self, timeout: float) -> None:
        """Wait for the reader thread to finish."""
        self._thread.join(timeout)

    def _connect(
        self, address: tuple[str, int], timeout: float | None
    ) -> socket.socket:
        """Open a relay socket that stop() can shut down."""
        sock = socket.create_connection(address, timeout)
        with self._lock:
            if self._stop.is_set():
                sock.close()
                raise OSError("VTM relay stopped")
            self._sockets.append(sock)
        return sock

    def _put(self, item: bytes | None) -> bool:
        """Queue an item, waiting for space; return False once stopped."""
        future = asyncio.run_coroutine_threadsafe(self._queue.put(item), self._loop)
        while True:
            try:
                future.result(QUEUE_PUT_TIMEOUT)
            except TimeoutError:
                if self._stop.is_set():
                    future.cancel()
                    return False
            else:
                return True

    def _run(self) -> None:
        """Copy relay packet bodies to the queue until stopped or closed."""
        try:
            with open_cloud_stream(
                self._client, self._serial, socket_factory=self._connect
            ) as stream:
                stream.start()
                for packet in stream.iter_packets():
                    if self._stop.is_set():
                        break
                    if packet.encrypted:
                        _LOGGER.error(
                            "%s: VTM stream is encrypted, which is not supported;"
                            " disable video encryption in the EZVIZ app",
                            self._serial,
                        )
                        break
                    if packet.body and not self._put(packet.body):
                        break
        except (PyEzvizError, OSError) as err:
            if not self._stop.is_set():
                _LOGGER.warning("%s: VTM stream failed: %s", self._serial, err)
        finally:
            if not self._stop.is_set():
                with suppress(RuntimeError):  # event loop already closed
                    self._put(None)


async def _feed_ffmpeg(
    queue: asyncio.Queue[bytes | None], stdin: asyncio.StreamWriter
) -> None:
    """Write relay payloads to FFmpeg; closing stdin ends the remux."""
    try:
        while (payload := await queue.get()) is not None:
            stdin.write(payload)
            await stdin.drain()
    except BrokenPipeError, ConnectionResetError:
        pass
    finally:
        stdin.close()
