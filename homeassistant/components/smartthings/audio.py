"""Audio helper for SmartThings audio notifications."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
import io
import logging
import secrets
import wave

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
PCM_MIME = "audio/wav"
PCM_EXTENSION = ".pcm"
BYTES_PER_SECOND = PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * PCM_CHANNELS
MAX_DURATION_SECONDS = 50
ENTRY_TTL = timedelta(minutes=5)
MAX_STORED_ENTRIES = 8

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
        pcm, duration = await self._transcode_to_pcm(source_url)
        if not pcm:
            raise SmartThingsAudioError("Converted audio is empty")

        if duration > MAX_DURATION_SECONDS:
            _LOGGER.warning(
                "SmartThings audio notification exceeds %s seconds (%.1fs); playback will be truncated",
                MAX_DURATION_SECONDS,
                duration,
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
                allow_internal=False,
                allow_external=True,
                allow_cloud=True,
                prefer_external=True,
                prefer_cloud=True,
            )
            url = f"{base_url}{path}"
        except NoURLAvailableError as err:
            async with self._lock:
                self._entries.pop(token, None)
            raise SmartThingsAudioError(
                "SmartThings audio notifications require an externally accessible URL"
            ) from err

        return url

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

    async def _transcode_to_pcm(self, source_url: str) -> tuple[bytes, float]:
        """Use ffmpeg to convert the source media to 24kHz mono PCM WAV."""
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
            "-f",
            "wav",
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
            return b"", 0.0

        wav_io = io.BytesIO(stdout)
        try:
            with wave.open(wav_io) as wav_in:
                frame_rate = wav_in.getframerate()
                frames = wav_in.getnframes()
                channels = wav_in.getnchannels()
                sample_width = wav_in.getsampwidth()
                if (
                    frame_rate != PCM_SAMPLE_RATE
                    or channels != PCM_CHANNELS
                    or sample_width != PCM_SAMPLE_WIDTH
                ):
                    _LOGGER.debug(
                        "SmartThings audio conversion produced unexpected format: %sHz %s channel(s) width=%s",
                        frame_rate,
                        channels,
                        sample_width,
                    )
        except wave.Error as err:
            _LOGGER.error(
                "Converted SmartThings audio is not a valid PCM WAV: %s",
                err,
            )
            raise SmartThingsAudioError(
                "Unable to convert audio to PCM for SmartThings"
            ) from err

        duration = frames / frame_rate if frame_rate else 0
        return stdout, duration

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
