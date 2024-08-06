"""HTTP view that converts audio from a URL to a preferred format."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
from aiohttp.abc import AbstractStreamWriter, BaseRequest
import voluptuous as vol

from homeassistant.components.ffmpeg import FFmpegManager
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DATA_FFMPEG_PROXY

_LOGGER = logging.getLogger(__name__)


def async_allow_proxy_url(hass: HomeAssistant, device_id: str, url: str) -> None:
    """Mark a URL as allowed for conversion by a specific device.

    The URL will be removed from the allow list once it is requested in the HTTP
    view.
    """
    data: FFmpegProxyData = hass.data[DATA_FFMPEG_PROXY]
    data.device_urls[device_id].add(url)
    _LOGGER.debug("URL allowed for device %s: %s", device_id, url)


@dataclass
class FFmpegProxyData:
    """Data for ffmpeg proxy conversion."""

    device_urls: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


class FFmpegConvertResponse(web.StreamResponse):
    """HTTP streaming response that uses ffmpeg to convert audio from a URL."""

    def __init__(
        self,
        manager: FFmpegManager,
        url: str,
        fmt: str,
        rate: int | None,
        channels: int | None,
        chunk_size: int = 2048,
    ) -> None:
        """Initialize response.

        Parameters
        ----------
        manager: FFmpegManager
            ffmpeg manager
        url: str
            URL of source audio stream
        fmt: str
            Target format of audio (flac, mp3, wav, etc.)
        rate: int, optional
            Target sample rate in hertz (None = same as source)
        channels: int, optional
            Target number of channels (None = same as source)
        chunk_size: int
            Number of bytes to read from ffmpeg process at a time

        """
        super().__init__(status=200)
        self.manager = manager
        self.url = url
        self.fmt = fmt
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size

    async def prepare(self, request: BaseRequest) -> AbstractStreamWriter | None:
        """Stream url through ffmpeg conversion and out to HTTP client."""
        writer = await super().prepare(request)
        assert writer is not None

        command_args = ["-i", self.url, "-f", self.fmt]

        if self.rate is not None:
            # Sample rate
            command_args.extend(["-ar", str(self.rate)])

        if self.channels is not None:
            # Number of channels
            command_args.extend(["-ac", str(self.channels)])

        # Output to stdout
        command_args.append("pipe:")

        _LOGGER.debug("%s %s", self.manager.binary, " ".join(command_args))
        proc = await asyncio.create_subprocess_exec(
            self.manager.binary,
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert proc.stdout is not None
        assert proc.stderr is not None
        try:
            # Pull audio chunks from ffmpeg and pass them to the HTTP client
            while chunk := await proc.stdout.read(self.chunk_size):
                await writer.write(chunk)

            # Try to gracefully stop
            proc.terminate()
            await proc.wait()
        finally:
            await writer.write_eof()

            if proc.returncode != 0:
                # Process did not exit successfully
                stderr_text = ""
                while line := await proc.stderr.readline():
                    stderr_text += line.decode()
                _LOGGER.error(stderr_text)
            else:
                _LOGGER.debug("Conversion completed: %s", self.url)

        return writer


class FFmpegProxyView(HomeAssistantView):
    """FFmpeg web view to convert audio and stream back to client."""

    requires_auth = False
    url = "/api/esphome/ffmpeg_proxy"
    name = "api:esphome:ffmpeg_proxy"

    schema = vol.Schema(
        {
            vol.Required("device_id"): cv.string,
            vol.Required("url"): cv.string,
            vol.Required("format"): cv.string,
            vol.Optional("rate"): cv.positive_int,
            vol.Optional("channels"): cv.positive_int,
        }
    )

    def __init__(self, manager: FFmpegManager, data: FFmpegProxyData) -> None:
        """Initialize an ffmpeg view."""
        self.manager = manager
        self.data = data

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Start a get request."""

        try:
            query: dict[str, Any] = self.schema(dict(request.query))
        except vol.Invalid as err:
            _LOGGER.error("Query does not match schema: %s", err)
            return web.Response(body=str(err), status=HTTPStatus.BAD_REQUEST)

        device_id = query["device_id"]
        url = query["url"]
        fmt = query["format"]

        rate: int | None = query.get("rate")
        channels: int | None = query.get("channels")

        try:
            self.data.device_urls[device_id].remove(url)
        except KeyError:
            _LOGGER.error("URL is not allowed for device %s: %s", device_id, url)
            return web.Response(body="URL not allowed", status=HTTPStatus.BAD_REQUEST)

        # Stream converted audio back to client
        return FFmpegConvertResponse(
            self.manager, url=url, fmt=fmt, rate=rate, channels=channels
        )
