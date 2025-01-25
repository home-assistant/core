"""HTTP view that converts audio from a URL to a preferred format."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from http import HTTPStatus
import logging
import secrets
from typing import Final

from aiohttp import web
from aiohttp.abc import AbstractStreamWriter, BaseRequest

from homeassistant.components.ffmpeg import FFmpegManager
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DATA_FFMPEG_PROXY

_LOGGER = logging.getLogger(__name__)

_MAX_CONVERSIONS_PER_DEVICE: Final[int] = 2


def async_create_proxy_url(
    hass: HomeAssistant,
    device_id: str,
    media_url: str,
    media_format: str,
    rate: int | None = None,
    channels: int | None = None,
    width: int | None = None,
) -> str:
    """Create a use proxy URL that automatically converts the media."""
    data: FFmpegProxyData = hass.data[DATA_FFMPEG_PROXY]
    return data.async_create_proxy_url(
        device_id, media_url, media_format, rate, channels, width
    )


@dataclass
class FFmpegConversionInfo:
    """Information for ffmpeg conversion."""

    convert_id: str
    """Unique id for media conversion."""

    media_url: str
    """Source URL of media to convert."""

    media_format: str
    """Target format for media (mp3, flac, etc.)"""

    rate: int | None
    """Target sample rate (None to keep source rate)."""

    channels: int | None
    """Target number of channels (None to keep source channels)."""

    width: int | None
    """Target sample width in bytes (None to keep source width)."""

    proc: asyncio.subprocess.Process | None = None
    """Subprocess doing ffmpeg conversion."""

    is_finished: bool = False
    """True if conversion has finished."""


@dataclass
class FFmpegProxyData:
    """Data for ffmpeg proxy conversion."""

    # device_id -> [info]
    conversions: dict[str, list[FFmpegConversionInfo]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def async_create_proxy_url(
        self,
        device_id: str,
        media_url: str,
        media_format: str,
        rate: int | None,
        channels: int | None,
        width: int | None,
    ) -> str:
        """Create a one-time use proxy URL that automatically converts the media."""

        # Remove completed conversions
        device_conversions = [
            info for info in self.conversions[device_id] if not info.is_finished
        ]

        while len(device_conversions) >= _MAX_CONVERSIONS_PER_DEVICE:
            # Stop oldest conversion before adding a new one
            convert_info = device_conversions[0]
            if (convert_info.proc is not None) and (
                convert_info.proc.returncode is None
            ):
                _LOGGER.debug(
                    "Stopping existing ffmpeg process for device: %s", device_id
                )
                convert_info.proc.kill()

            device_conversions = device_conversions[1:]

        convert_id = secrets.token_urlsafe(16)
        device_conversions.append(
            FFmpegConversionInfo(
                convert_id, media_url, media_format, rate, channels, width
            )
        )
        _LOGGER.debug("Media URL allowed by proxy: %s", media_url)

        self.conversions[device_id] = device_conversions

        return f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.{media_format}"


class FFmpegConvertResponse(web.StreamResponse):
    """HTTP streaming response that uses ffmpeg to convert audio from a URL."""

    def __init__(
        self,
        manager: FFmpegManager,
        convert_info: FFmpegConversionInfo,
        device_id: str,
        proxy_data: FFmpegProxyData,
        chunk_size: int = 2048,
    ) -> None:
        """Initialize response.

        Parameters
        ----------
        manager: FFmpegManager
            ffmpeg manager
        convert_info: FFmpegConversionInfo
            Information necessary to do the conversion
        device_id: str
            ESPHome device id
        proxy_data: FFmpegProxyData
            Data object to store ffmpeg process
        chunk_size: int
            Number of bytes to read from ffmpeg process at a time

        """
        super().__init__(status=200)
        self.hass = manager.hass
        self.manager = manager
        self.convert_info = convert_info
        self.device_id = device_id
        self.proxy_data = proxy_data
        self.chunk_size = chunk_size

    async def transcode(
        self, request: BaseRequest, writer: AbstractStreamWriter
    ) -> None:
        """Stream url through ffmpeg conversion and out to HTTP client."""
        command_args = [
            "-i",
            self.convert_info.media_url,
            "-f",
            self.convert_info.media_format,
        ]

        if self.convert_info.rate is not None:
            # Sample rate
            command_args.extend(["-ar", str(self.convert_info.rate)])

        if self.convert_info.channels is not None:
            # Number of channels
            command_args.extend(["-ac", str(self.convert_info.channels)])

        if self.convert_info.width == 2:
            # 16-bit samples
            command_args.extend(["-sample_fmt", "s16"])

        # Remove metadata and cover art
        command_args.extend(["-map_metadata", "-1", "-vn"])

        # disable progress stats on stderr
        command_args.append("-nostats")

        # Output to stdout
        command_args.append("pipe:")

        _LOGGER.debug("%s %s", self.manager.binary, " ".join(command_args))
        proc = await asyncio.create_subprocess_exec(
            self.manager.binary,
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            close_fds=False,  # use posix_spawn in CPython < 3.13
        )

        # Only one conversion process per device is allowed
        self.convert_info.proc = proc

        # Create background task which will be cancelled when home assistant shuts down
        write_task = self.hass.async_create_background_task(
            self._write_ffmpeg_data(request, writer, proc), "ESPHome media proxy"
        )
        await write_task

    async def _write_ffmpeg_data(
        self,
        request: BaseRequest,
        writer: AbstractStreamWriter,
        proc: asyncio.subprocess.Process,
    ) -> None:
        assert proc.stdout is not None
        assert proc.stderr is not None

        stderr_task = self.hass.async_create_background_task(
            self._dump_ffmpeg_stderr(proc), "ESPHome media proxy dump stderr"
        )

        try:
            # Pull audio chunks from ffmpeg and pass them to the HTTP client
            while (
                self.hass.is_running
                and (request.transport is not None)
                and (not request.transport.is_closing())
                and (chunk := await proc.stdout.read(self.chunk_size))
            ):
                await self.write(chunk)
        except asyncio.CancelledError:
            _LOGGER.debug("ffmpeg transcoding cancelled")
            # Abort the transport, we don't wait for ESPHome to drain the write buffer;
            # it may need a very long time or never finish if the player is paused.
            if request.transport:
                request.transport.abort()
            raise  # don't log error
        except:
            _LOGGER.exception("Unexpected error during ffmpeg conversion")
            raise
        finally:
            # Allow conversion info to be removed
            self.convert_info.is_finished = True

            # stop dumping ffmpeg stderr task
            stderr_task.cancel()

            # Terminate hangs, so kill is used
            if proc.returncode is None:
                proc.kill()

            # Close connection by writing EOF unless already closing
            if request.transport and not request.transport.is_closing():
                await writer.write_eof()

    async def _dump_ffmpeg_stderr(
        self,
        proc: asyncio.subprocess.Process,
    ) -> None:
        assert proc.stdout is not None
        assert proc.stderr is not None

        while self.hass.is_running and (chunk := await proc.stderr.readline()):
            _LOGGER.debug("ffmpeg[%s] output: %s", proc.pid, chunk.decode().rstrip())


class FFmpegProxyView(HomeAssistantView):
    """FFmpeg web view to convert audio and stream back to client."""

    requires_auth = False
    url = "/api/esphome/ffmpeg_proxy/{device_id}/{filename}"
    name = "api:esphome:ffmpeg_proxy"

    def __init__(self, manager: FFmpegManager, proxy_data: FFmpegProxyData) -> None:
        """Initialize an ffmpeg view."""
        self.manager = manager
        self.proxy_data = proxy_data

    async def get(
        self, request: web.Request, device_id: str, filename: str
    ) -> web.StreamResponse:
        """Start a get request."""
        device_conversions = self.proxy_data.conversions[device_id]
        if not device_conversions:
            return web.Response(
                body="No proxy URL for device", status=HTTPStatus.NOT_FOUND
            )

        # {id}.mp3 -> id, mp3
        convert_id, media_format = filename.rsplit(".")

        # Look up conversion info
        convert_info: FFmpegConversionInfo | None = None
        for maybe_convert_info in device_conversions:
            if (maybe_convert_info.convert_id == convert_id) and (
                maybe_convert_info.media_format == media_format
            ):
                convert_info = maybe_convert_info
                break

        if convert_info is None:
            return web.Response(body="Invalid proxy URL", status=HTTPStatus.BAD_REQUEST)

        # Stop previous process if the URL is being reused.
        # We could continue from where the previous connection left off, but
        # there would be no media header.
        if (convert_info.proc is not None) and (convert_info.proc.returncode is None):
            convert_info.proc.kill()
            convert_info.proc = None

        # Stream converted audio back to client
        resp = FFmpegConvertResponse(
            self.manager, convert_info, device_id, self.proxy_data
        )
        writer = await resp.prepare(request)
        assert writer is not None
        await resp.transcode(request, writer)
        return resp
