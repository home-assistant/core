"""Serve the EZVIZ VTM cloud relay stream as MPEG-TS over the local HA HTTP server.

Many EZVIZ devices (battery cameras, doorbells, newer firmware) no longer expose
RTSP. The EZVIZ apps still show live video through the VTM cloud relay, which
delivers MPEG-PS over TCP. This module opens that relay with pyezvizapi, remuxes
it to MPEG-TS with FFmpeg (codec copy, no transcoding) and serves it on a local
URL that the camera entity returns as its stream source.

The URL carries a random per-start access token instead of HA auth, because the
consumers (the stream worker and go2rtc) cannot send HA credentials.
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import hmac
import logging
import secrets
import threading

from aiohttp import web
from pyezvizapi.client import EzvizClient
from pyezvizapi.cloud_stream import open_cloud_stream
from pyezvizapi.exceptions import PyEzvizError

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

VTM_URL = "/api/ezviz/vtm/{access_token}/{serial}.ts"
READ_CHUNK = 65536


@dataclass
class EzvizVtmData:
    """Shared state for the VTM stream view."""

    access_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    # serial -> client of the account the camera belongs to
    clients: dict[str, EzvizClient] = field(default_factory=dict)


DATA_VTM: HassKey[EzvizVtmData] = HassKey(f"{DOMAIN}_vtm")


@callback
def async_setup_vtm(hass: HomeAssistant) -> EzvizVtmData:
    """Register the VTM stream view once and return the shared state."""
    if (data := hass.data.get(DATA_VTM)) is None:
        data = hass.data[DATA_VTM] = EzvizVtmData()
        hass.http.register_view(EzvizVtmStreamView())
    return data


def vtm_stream_url(hass: HomeAssistant, serial: str) -> str | None:
    """Return the loopback URL serving the VTM stream of a camera."""
    data = hass.data[DATA_VTM]
    if (api := hass.config.api) is None:
        return None
    scheme = "https" if api.use_ssl else "http"
    path = VTM_URL.format(access_token=data.access_token, serial=serial)
    return f"{scheme}://127.0.0.1:{api.port}{path}"


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

    async def get(
        self, request: web.Request, access_token: str, serial: str
    ) -> web.StreamResponse:
        """Open the relay and copy it to the HTTP client until it disconnects."""
        hass = request.app[KEY_HASS]
        data = hass.data.get(DATA_VTM)
        if (
            data is None
            or not hmac.compare_digest(access_token, data.access_token)
            or (client := data.clients.get(serial)) is None
        ):
            raise web.HTTPNotFound

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
        stdin = process.stdin
        stdout = process.stdout
        if stdin is None or stdout is None:  # pragma: no cover - PIPE requested
            raise web.HTTPInternalServerError

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        stop = threading.Event()
        # The VTM client uses blocking sockets, so it gets its own thread
        # instead of holding an executor worker for the whole session.
        pump = threading.Thread(
            target=_pump_vtm,
            args=(client, serial, stop, loop, queue),
            name=f"ezviz_vtm_{serial}",
            daemon=True,
        )
        pump.start()
        feeder = asyncio.create_task(_feed_ffmpeg(queue, stdin))

        response = web.StreamResponse(
            headers={"Content-Type": "video/MP2T", "Cache-Control": "no-store"}
        )
        _LOGGER.debug("%s: VTM stream opened", serial)
        try:
            await response.prepare(request)
            while chunk := await stdout.read(READ_CHUNK):
                await response.write(chunk)
        except ConnectionResetError:
            pass
        finally:
            stop.set()
            feeder.cancel()
            if process.returncode is None:
                process.kill()
            await process.wait()
            _LOGGER.debug("%s: VTM stream closed", serial)
        return response


def _pump_vtm(
    client: EzvizClient,
    serial: str,
    stop: threading.Event,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[bytes | None],
) -> None:
    """Read VTM packets in a worker thread and hand their payloads to the loop."""
    try:
        with open_cloud_stream(client, serial) as stream:
            stream.start()
            for packet in stream.iter_packets():
                if stop.is_set():
                    break
                if packet.encrypted:
                    _LOGGER.error(
                        "%s: VTM stream is encrypted, which is not supported;"
                        " disable video encryption in the EZVIZ app",
                        serial,
                    )
                    break
                if packet.body:
                    loop.call_soon_threadsafe(queue.put_nowait, packet.body)
    except (PyEzvizError, OSError) as err:
        if not stop.is_set():
            _LOGGER.warning("%s: VTM stream failed: %s", serial, err)
    finally:
        with suppress(RuntimeError):  # event loop already closed
            loop.call_soon_threadsafe(queue.put_nowait, None)


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
