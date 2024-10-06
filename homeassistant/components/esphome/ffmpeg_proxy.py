"""HTTP view that converts audio from a URL to a preferred format."""

import asyncio
from dataclasses import dataclass, field
from http import HTTPStatus
import logging
import secrets

from aiohttp import web
from aiohttp.abc import AbstractStreamWriter, BaseRequest

from homeassistant.components.ffmpeg import FFmpegManager
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DATA_FFMPEG_PROXY

_LOGGER = logging.getLogger(__name__)


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


@dataclass
class FFmpegProxyData:
    """Data for ffmpeg proxy conversion."""

    # device_id -> info
    conversions: dict[str, FFmpegConversionInfo] = field(default_factory=dict)

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
        if (convert_info := self.conversions.pop(device_id, None)) is not None:
            # Stop existing conversion before overwriting info
            if (convert_info.proc is not None) and (
                convert_info.proc.returncode is None
            ):
                _LOGGER.debug(
                    "Stopping existing ffmpeg process for device: %s", device_id
                )
                convert_info.proc.kill()

        convert_id = secrets.token_urlsafe(16)
        self.conversions[device_id] = FFmpegConversionInfo(
            convert_id, media_url, media_format, rate, channels, width
        )
        _LOGGER.debug("Media URL allowed by proxy: %s", media_url)

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

    async def prepare(self, request: BaseRequest) -> AbstractStreamWriter | None:
        """Stream url through ffmpeg conversion and out to HTTP client."""
        writer = await super().prepare(request)
        assert writer is not None

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

        # Output to stdout
        command_args.append("pipe:")

        _LOGGER.debug("%s %s", self.manager.binary, " ".join(command_args))
        proc = await asyncio.create_subprocess_exec(
            self.manager.binary,
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Only one conversion process per device is allowed
        self.convert_info.proc = proc

        assert proc.stdout is not None
        assert proc.stderr is not None

        try:
            # Pull audio chunks from ffmpeg and pass them to the HTTP client
            while (
                self.hass.is_running
                and (request.transport is not None)
                and (not request.transport.is_closing())
                and (proc.returncode is None)
                and (chunk := await proc.stdout.read(self.chunk_size))
            ):
                await writer.write(chunk)
                await writer.drain()
        except asyncio.CancelledError:
            raise  # don't log error
        except:
            _LOGGER.exception("Unexpected error during ffmpeg conversion")

            # Process did not exit successfully
            stderr_text = ""
            while line := await proc.stderr.readline():
                stderr_text += line.decode()
            _LOGGER.error("FFmpeg output: %s", stderr_text)

            raise
        finally:
            # Terminate hangs, so kill is used
            if proc.returncode is None:
                proc.kill()

            # Close connection
            await writer.write_eof()

        return writer


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
        if (convert_info := self.proxy_data.conversions.get(device_id)) is None:
            return web.Response(
                body="No proxy URL for device", status=HTTPStatus.NOT_FOUND
            )

        # {id}.mp3 -> id, mp3
        convert_id, media_format = filename.rsplit(".")

        if (convert_info.convert_id != convert_id) or (
            convert_info.media_format != media_format
        ):
            return web.Response(body="Invalid proxy URL", status=HTTPStatus.BAD_REQUEST)

        # Stop previous process if the URL is being reused.
        # We could continue from where the previous connection left off, but
        # there would be no media header.
        if (convert_info.proc is not None) and (convert_info.proc.returncode is None):
            convert_info.proc.kill()
            convert_info.proc = None

        # Stream converted audio back to client
        return FFmpegConvertResponse(
            self.manager, convert_info, device_id, self.proxy_data
        )
