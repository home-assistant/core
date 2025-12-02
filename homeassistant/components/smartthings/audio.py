"""Audio helper for SmartThings audio notifications."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import contextlib
from dataclasses import dataclass
from datetime import timedelta
import logging
import secrets

from aiohttp import web

from homeassistant.components import ffmpeg
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PCM_SAMPLE_RATE = 24000
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1
PCM_MIME = "audio/L16"
PCM_EXTENSION = ".pcm"
WARNING_DURATION_SECONDS = 40
FFMPEG_MAX_DURATION_SECONDS = 10 * 60
TRANSCODE_TIMEOUT_SECONDS = WARNING_DURATION_SECONDS + 10
_TRUNCATION_EPSILON = 1 / PCM_SAMPLE_RATE
ENTRY_TTL = timedelta(minutes=5)
MAX_STORED_ENTRIES = 8

PCM_FRAME_BYTES = PCM_SAMPLE_WIDTH * PCM_CHANNELS

DATA_AUDIO_MANAGER = "audio_manager"


class SmartThingsAudioError(HomeAssistantError):
    """Error raised when SmartThings audio preparation fails."""


@dataclass
class _AudioEntry:
    """Stored PCM audio entry."""

    pcm: bytes
    created: float
    expires: float


class SmartThingsAudioManager(HomeAssistantView):
    """Manage PCM proxy URLs for SmartThings audio notifications."""

    url = "/api/smartthings/audio/{token}"
    name = "api:smartthings:audio"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._entries: OrderedDict[str, _AudioEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def async_prepare_notification(self, source_url: str) -> str:
        """Generate an externally accessible PCM URL for SmartThings."""
        pcm, duration, truncated = await self._transcode_to_pcm(source_url)
        if not pcm:
            raise SmartThingsAudioError("Converted audio is empty")

        if truncated:
            _LOGGER.warning(
                "SmartThings audio notification truncated to %s seconds (output length %.1fs); longer sources may be cut off",
                FFMPEG_MAX_DURATION_SECONDS,
                duration,
            )
        elif duration > WARNING_DURATION_SECONDS:
            _LOGGER.warning(
                "SmartThings audio notification is %.1fs; playback over %s seconds may be cut off",
                duration,
                WARNING_DURATION_SECONDS,
            )

        token = secrets.token_urlsafe(16)
        now = dt_util.utcnow().timestamp()
        entry = _AudioEntry(
            pcm=pcm,
            created=now,
            expires=now + ENTRY_TTL.total_seconds(),
        )

        async with self._lock:
            self._cleanup(now)
            self._entries[token] = entry
            self._entries.move_to_end(token)
            while len(self._entries) > MAX_STORED_ENTRIES:
                dropped_token, _ = self._entries.popitem(last=False)
                _LOGGER.debug(
                    "Dropped expired SmartThings audio token %s", dropped_token
                )

        path = f"/api/smartthings/audio/{token}{PCM_EXTENSION}"
        try:
            base_url = get_url(
                self.hass,
                allow_internal=True,
                allow_external=True,
                allow_cloud=True,
                prefer_external=True,
                prefer_cloud=True,
            )
        except NoURLAvailableError as err:
            async with self._lock:
                self._entries.pop(token, None)
            raise SmartThingsAudioError(
                "SmartThings audio notifications require an accessible Home Assistant URL"
            ) from err

        return f"{base_url}{path}"

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Serve a PCM audio response."""
        token = token.removesuffix(PCM_EXTENSION)

        async with self._lock:
            now = dt_util.utcnow().timestamp()
            self._cleanup(now)
            entry = self._entries.get(token)

        if entry is None:
            raise web.HTTPNotFound

        _LOGGER.debug("Serving SmartThings audio token=%s to %s", token, request.remote)

        response = web.Response(body=entry.pcm, content_type=PCM_MIME)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Accept-Ranges"] = "none"
        response.headers["Content-Disposition"] = (
            f'inline; filename="{token}{PCM_EXTENSION}"'
        )
        return response

    async def _transcode_to_pcm(self, source_url: str) -> tuple[bytes, float, bool]:
        """Use ffmpeg to convert the source media to 24kHz mono PCM."""
        manager = ffmpeg.get_ffmpeg_manager(self.hass)
        command = [
            manager.binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            source_url,
            "-ac",
            str(PCM_CHANNELS),
            "-ar",
            str(PCM_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            "-t",
            str(FFMPEG_MAX_DURATION_SECONDS),
            "-f",
            "s16le",
            "pipe:1",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as err:
            raise SmartThingsAudioError(
                "FFmpeg is required for SmartThings audio notifications"
            ) from err

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=TRANSCODE_TIMEOUT_SECONDS
            )
        except TimeoutError:
            _LOGGER.warning(
                "FFmpeg timed out after %s seconds while converting SmartThings audio from %s",
                TRANSCODE_TIMEOUT_SECONDS,
                source_url,
            )
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            stdout, stderr = await process.communicate()

        if process.returncode != 0:
            message = stderr.decode().strip() or "unknown error"
            _LOGGER.error(
                "FFmpeg failed to convert SmartThings audio from %s: %s",
                source_url,
                message,
            )
            raise SmartThingsAudioError(
                "Unable to convert audio to PCM for SmartThings"
            )

        if not stdout:
            return b"", 0.0, False

        frame_count, remainder = divmod(len(stdout), PCM_FRAME_BYTES)
        if remainder:
            _LOGGER.debug(
                "SmartThings audio conversion produced misaligned PCM: dropping %s extra byte(s)",
                remainder,
            )
            stdout = stdout[: len(stdout) - remainder]
            frame_count = len(stdout) // PCM_FRAME_BYTES

        if frame_count == 0:
            return b"", 0.0, False

        duration = frame_count / PCM_SAMPLE_RATE
        truncated = duration >= (FFMPEG_MAX_DURATION_SECONDS - _TRUNCATION_EPSILON)
        return stdout, duration, truncated

    def _cleanup(self, now: float) -> None:
        """Remove expired entries."""
        expired = [
            token for token, entry in self._entries.items() if entry.expires <= now
        ]
        for token in expired:
            self._entries.pop(token, None)


async def async_get_audio_manager(hass: HomeAssistant) -> SmartThingsAudioManager:
    """Return the shared SmartThings audio manager."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if (manager := domain_data.get(DATA_AUDIO_MANAGER)) is None:
        manager = SmartThingsAudioManager(hass)
        hass.http.register_view(manager)
        domain_data[DATA_AUDIO_MANAGER] = manager
    return manager
