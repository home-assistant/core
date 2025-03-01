"""Provide functionality for TTS."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import hashlib
from http import HTTPStatus
import io
import logging
import mimetypes
import os
import re
import secrets
import subprocess
import tempfile
from time import monotonic
from typing import Any, Final, TypedDict

from aiohttp import web
import mutagen
from mutagen.id3 import ID3, TextFrame as ID3Text
from propcache.api import cached_property
import voluptuous as vol

from homeassistant.components import ffmpeg, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, PLATFORM_FORMAT
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import UNDEFINED, ConfigType
from homeassistant.util import language as language_util

from .const import (
    ATTR_CACHE,
    ATTR_LANGUAGE,
    ATTR_MESSAGE,
    ATTR_OPTIONS,
    CONF_CACHE,
    CONF_CACHE_DIR,
    CONF_TIME_MEMORY,
    DATA_COMPONENT,
    DATA_TTS_MANAGER,
    DEFAULT_CACHE,
    DEFAULT_CACHE_DIR,
    DEFAULT_TIME_MEMORY,
    DOMAIN,
    TtsAudioType,
)
from .entity import TextToSpeechEntity
from .helper import get_engine_instance
from .legacy import PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE, Provider, async_setup_legacy
from .media_source import generate_media_source_id, media_source_id_to_kwargs
from .models import Voice

__all__ = [
    "ATTR_AUDIO_OUTPUT",
    "ATTR_PREFERRED_FORMAT",
    "ATTR_PREFERRED_SAMPLE_BYTES",
    "ATTR_PREFERRED_SAMPLE_CHANNELS",
    "ATTR_PREFERRED_SAMPLE_RATE",
    "CONF_LANG",
    "DEFAULT_CACHE_DIR",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "Provider",
    "SampleFormat",
    "TextToSpeechEntity",
    "TtsAudioType",
    "Voice",
    "async_default_engine",
    "async_get_media_source_audio",
    "async_support_options",
    "generate_media_source_id",
]

_LOGGER = logging.getLogger(__name__)

ATTR_PLATFORM = "platform"
ATTR_AUDIO_OUTPUT = "audio_output"
ATTR_PREFERRED_FORMAT = "preferred_format"
ATTR_PREFERRED_SAMPLE_RATE = "preferred_sample_rate"
ATTR_PREFERRED_SAMPLE_CHANNELS = "preferred_sample_channels"
ATTR_PREFERRED_SAMPLE_BYTES = "preferred_sample_bytes"
ATTR_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"
ATTR_VOICE = "voice"

_DEFAULT_FORMAT = "mp3"
_PREFFERED_FORMAT_OPTIONS: Final[set[str]] = {
    ATTR_PREFERRED_FORMAT,
    ATTR_PREFERRED_SAMPLE_RATE,
    ATTR_PREFERRED_SAMPLE_CHANNELS,
    ATTR_PREFERRED_SAMPLE_BYTES,
}

CONF_LANG = "language"

SERVICE_CLEAR_CACHE = "clear_cache"

_RE_LEGACY_VOICE_FILE = re.compile(
    r"([a-f0-9]{40})_([^_]+)_([^_]+)_([a-z_]+)\.[a-z0-9]{3,4}"
)
_RE_VOICE_FILE = re.compile(
    r"([a-f0-9]{40})_([^_]+)_([^_]+)_(tts\.[a-z0-9_]+)\.[a-z0-9]{3,4}"
)
KEY_PATTERN = "{0}_{1}_{2}_{3}"

SCHEMA_SERVICE_CLEAR_CACHE = vol.Schema({})


class TTSCache(TypedDict):
    """Cached TTS file."""

    extension: str
    voice: bytes
    pending: asyncio.Task | None
    last_used: float


@callback
def async_default_engine(hass: HomeAssistant) -> str | None:
    """Return the domain or entity id of the default engine.

    Returns None if no engines found.
    """
    default_entity_id: str | None = None

    for entity in hass.data[DATA_COMPONENT].entities:
        if entity.platform and entity.platform.platform_name == "cloud":
            return entity.entity_id

        if default_entity_id is None:
            default_entity_id = entity.entity_id

    return default_entity_id or next(iter(hass.data[DATA_TTS_MANAGER].providers), None)


@callback
def async_resolve_engine(hass: HomeAssistant, engine: str | None) -> str | None:
    """Resolve engine.

    Returns None if no engines found or invalid engine passed in.
    """
    if engine is not None:
        if (
            not hass.data[DATA_COMPONENT].get_entity(engine)
            and engine not in hass.data[DATA_TTS_MANAGER].providers
        ):
            return None
        return engine

    return async_default_engine(hass)


async def async_support_options(
    hass: HomeAssistant,
    engine: str,
    language: str | None = None,
    options: dict | None = None,
) -> bool:
    """Return if an engine supports options."""
    if (engine_instance := get_engine_instance(hass, engine)) is None:
        raise HomeAssistantError(f"Provider {engine} not found")

    try:
        hass.data[DATA_TTS_MANAGER].process_options(engine_instance, language, options)
    except HomeAssistantError:
        return False

    return True


async def async_get_media_source_audio(
    hass: HomeAssistant,
    media_source_id: str,
) -> tuple[str, bytes]:
    """Get TTS audio as extension, data."""
    manager = hass.data[DATA_TTS_MANAGER]
    cache_key = manager.async_cache_message_in_memory(
        **media_source_id_to_kwargs(media_source_id)
    )
    return await manager.async_get_tts_audio(cache_key)


@callback
def async_get_text_to_speech_languages(hass: HomeAssistant) -> set[str]:
    """Return a set with the union of languages supported by tts engines."""
    languages = set()

    for entity in hass.data[DATA_COMPONENT].entities:
        for language_tag in entity.supported_languages:
            languages.add(language_tag)

    for tts_engine in hass.data[DATA_TTS_MANAGER].providers.values():
        for language_tag in tts_engine.supported_languages:
            languages.add(language_tag)

    return languages


async def async_convert_audio(
    hass: HomeAssistant,
    from_extension: str,
    audio_bytes: bytes,
    to_extension: str,
    to_sample_rate: int | None = None,
    to_sample_channels: int | None = None,
    to_sample_bytes: int | None = None,
) -> bytes:
    """Convert audio to a preferred format using ffmpeg."""
    ffmpeg_manager = ffmpeg.get_ffmpeg_manager(hass)
    return await hass.async_add_executor_job(
        lambda: _convert_audio(
            ffmpeg_manager.binary,
            from_extension,
            audio_bytes,
            to_extension,
            to_sample_rate=to_sample_rate,
            to_sample_channels=to_sample_channels,
            to_sample_bytes=to_sample_bytes,
        )
    )


def _convert_audio(
    ffmpeg_binary: str,
    from_extension: str,
    audio_bytes: bytes,
    to_extension: str,
    to_sample_rate: int | None = None,
    to_sample_channels: int | None = None,
    to_sample_bytes: int | None = None,
) -> bytes:
    """Convert audio to a preferred format using ffmpeg."""

    # We have to use a temporary file here because some formats like WAV store
    # the length of the file in the header, and therefore cannot be written in a
    # streaming fashion.
    with tempfile.NamedTemporaryFile(
        mode="wb+", suffix=f".{to_extension}"
    ) as output_file:
        # input
        command = [
            ffmpeg_binary,
            "-y",  # overwrite temp file
            "-f",
            from_extension,
            "-i",
            "pipe:",  # input from stdin
        ]

        # output
        command.extend(["-f", to_extension])

        if to_sample_rate is not None:
            command.extend(["-ar", str(to_sample_rate)])

        if to_sample_channels is not None:
            command.extend(["-ac", str(to_sample_channels)])

        if to_extension == "mp3":
            # Max quality for MP3
            command.extend(["-q:a", "0"])

        if to_sample_bytes == 2:
            # 16-bit samples
            command.extend(["-sample_fmt", "s16"])

        command.append(output_file.name)

        with subprocess.Popen(
            command, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        ) as proc:
            _stdout, stderr = proc.communicate(input=audio_bytes)
            if proc.returncode != 0:
                _LOGGER.error(stderr.decode())
                raise RuntimeError(
                    f"Unexpected error while running ffmpeg with arguments: {command}."
                    "See log for details."
                )

        output_file.seek(0)
        return output_file.read()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up TTS."""
    websocket_api.async_register_command(hass, websocket_list_engines)
    websocket_api.async_register_command(hass, websocket_get_engine)
    websocket_api.async_register_command(hass, websocket_list_engine_voices)

    # Legacy config options
    conf = config[DOMAIN][0] if config.get(DOMAIN) else {}
    use_file_cache: bool = conf.get(CONF_CACHE, DEFAULT_CACHE)
    cache_dir: str = conf.get(CONF_CACHE_DIR, DEFAULT_CACHE_DIR)
    memory_cache_maxage: int = conf.get(CONF_TIME_MEMORY, DEFAULT_TIME_MEMORY)

    tts = SpeechManager(hass, use_file_cache, cache_dir, memory_cache_maxage)

    try:
        await tts.async_init_cache()
    except (HomeAssistantError, KeyError):
        _LOGGER.exception("Error on cache init")
        return False

    hass.data[DATA_TTS_MANAGER] = tts
    component = hass.data[DATA_COMPONENT] = EntityComponent[TextToSpeechEntity](
        _LOGGER, DOMAIN, hass
    )

    component.register_shutdown()

    hass.http.register_view(TextToSpeechView(tts))
    hass.http.register_view(TextToSpeechUrlView(tts))

    platform_setups = await async_setup_legacy(hass, config)

    component.async_register_entity_service(
        "speak",
        {
            vol.Required(ATTR_MEDIA_PLAYER_ENTITY_ID): cv.comp_entity_ids,
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_CACHE, default=DEFAULT_CACHE): cv.boolean,
            vol.Optional(ATTR_LANGUAGE): cv.string,
            vol.Optional(ATTR_OPTIONS): dict,
        },
        "async_speak",
    )

    async def async_clear_cache_handle(service: ServiceCall) -> None:
        """Handle clear cache service call."""
        await tts.async_clear_cache()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        async_clear_cache_handle,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )

    for setup in platform_setups:
        # Tasks are created as tracked tasks to ensure startup
        # waits for them to finish, but we explicitly do not
        # want to wait for them to finish here because we want
        # any config entries that use tts as a base platform
        # to be able to start with out having to wait for the
        # legacy platforms to finish setting up.
        hass.async_create_task(setup, eager_start=True)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@dataclass
class ResultStream:
    """Class that will stream the result when available."""

    # Streaming/conversion properties
    token: str
    extension: str
    content_type: str

    # TTS properties
    engine: str
    use_file_cache: bool
    language: str
    options: dict

    _manager: SpeechManager

    @cached_property
    def url(self) -> str:
        """Get the URL to stream the result."""
        return f"/api/tts_proxy/{self.token}"

    @cached_property
    def _result_cache_key(self) -> asyncio.Future[str]:
        """Get the future that returns the cache key."""
        return asyncio.Future()

    @callback
    def async_set_message_cache_key(self, cache_key: str) -> None:
        """Set cache key for message to be streamed."""
        self._result_cache_key.set_result(cache_key)

    async def async_stream_result(self) -> AsyncGenerator[bytes]:
        """Get the stream of this result."""
        cache_key = await self._result_cache_key
        _extension, data = await self._manager.async_get_tts_audio(cache_key)
        yield data


def _hash_options(options: dict) -> str:
    """Hashes an options dictionary."""
    opts_hash = hashlib.blake2s(digest_size=5)
    for key, value in sorted(options.items()):
        opts_hash.update(str(key).encode())
        opts_hash.update(str(value).encode())

    return opts_hash.hexdigest()


class MemcacheCleanup:
    """Helper to clean up the stale sessions."""

    unsub: CALLBACK_TYPE | None = None

    def __init__(
        self, hass: HomeAssistant, maxage: float, memcache: dict[str, TTSCache]
    ) -> None:
        """Initialize the cleanup."""
        self.hass = hass
        self.maxage = maxage
        self.memcache = memcache
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_hass_stop)
        self.cleanup_job = HassJob(
            self._cleanup, "chat_session_cleanup", job_type=HassJobType.Callback
        )

    @callback
    def schedule(self) -> None:
        """Schedule the cleanup."""
        if self.unsub:
            return
        self.unsub = async_call_later(
            self.hass,
            self.maxage + 1,
            self.cleanup_job,
        )

    @callback
    def _on_hass_stop(self, event: Event) -> None:
        """Cancel the cleanup on shutdown."""
        if self.unsub:
            self.unsub()
        self.unsub = None

    @callback
    def _cleanup(self, _now: datetime) -> None:
        """Clean up and schedule follow-up if necessary."""
        self.unsub = None
        memcache = self.memcache
        maxage = self.maxage
        now = monotonic()

        for cache_key, info in list(memcache.items()):
            if info["last_used"] + maxage < now:
                _LOGGER.debug("Cleaning up %s", cache_key)
                del memcache[cache_key]

        # Still items left, check again in timeout time.
        if memcache:
            self.schedule()


class SpeechManager:
    """Representation of a speech store."""

    def __init__(
        self,
        hass: HomeAssistant,
        use_file_cache: bool,
        cache_dir: str,
        memory_cache_maxage: int,
    ) -> None:
        """Initialize a speech store."""
        self.hass = hass
        self.providers: dict[str, Provider] = {}

        self.use_file_cache = use_file_cache
        self.cache_dir = cache_dir
        self.memory_cache_maxage = memory_cache_maxage
        self.file_cache: dict[str, str] = {}
        self.mem_cache: dict[str, TTSCache] = {}
        self.token_to_stream: dict[str, ResultStream] = {}
        self.memcache_cleanup = MemcacheCleanup(
            hass, memory_cache_maxage, self.mem_cache
        )

    def _init_cache(self) -> dict[str, str]:
        """Init cache folder and fetch files."""
        try:
            self.cache_dir = _init_tts_cache_dir(self.hass, self.cache_dir)
        except OSError as err:
            raise HomeAssistantError(f"Can't init cache dir {err}") from err

        try:
            return _get_cache_files(self.cache_dir)
        except OSError as err:
            raise HomeAssistantError(f"Can't read cache dir {err}") from err

    async def async_init_cache(self) -> None:
        """Init config folder and load file cache."""
        self.file_cache.update(await self.hass.async_add_executor_job(self._init_cache))

    async def async_clear_cache(self) -> None:
        """Read file cache and delete files."""
        self.mem_cache.clear()

        def remove_files(files: list[str]) -> None:
            """Remove files from filesystem."""
            for filename in files:
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError as err:
                    _LOGGER.warning("Can't remove cache file '%s': %s", filename, err)

        task = self.hass.async_add_executor_job(
            remove_files, list(self.file_cache.values())
        )
        self.file_cache.clear()
        await task

    @callback
    def async_register_legacy_engine(
        self, engine: str, provider: Provider, config: ConfigType
    ) -> None:
        """Register a legacy TTS engine."""
        provider.hass = self.hass
        if provider.name is None:
            provider.name = engine
        self.providers[engine] = provider

        self.hass.config.components.add(
            PLATFORM_FORMAT.format(domain=DOMAIN, platform=engine)
        )

    @callback
    def process_options(
        self,
        engine_instance: TextToSpeechEntity | Provider,
        language: str | None,
        options: dict | None,
    ) -> tuple[str, dict[str, Any]]:
        """Validate and process options."""
        # Languages
        language = language or engine_instance.default_language
        if (
            language is None
            or engine_instance.supported_languages is None
            or language not in engine_instance.supported_languages
        ):
            raise HomeAssistantError(f"Language '{language}' not supported")

        options = options or {}
        supported_options = engine_instance.supported_options or []

        # Update default options with provided options
        invalid_opts: list[str] = []
        merged_options = dict(engine_instance.default_options or {})
        for option_name, option_value in options.items():
            # Only count an option as invalid if it's not a "preferred format"
            # option. These are used as hints to the TTS system if supported,
            # and otherwise as parameters to ffmpeg conversion.
            if (option_name in supported_options) or (
                option_name in _PREFFERED_FORMAT_OPTIONS
            ):
                merged_options[option_name] = option_value
            else:
                invalid_opts.append(option_name)

        if invalid_opts:
            raise HomeAssistantError(f"Invalid options found: {invalid_opts}")

        return language, merged_options

    @callback
    def async_create_result_stream(
        self,
        engine: str,
        message: str | None = None,
        use_file_cache: bool | None = None,
        language: str | None = None,
        options: dict | None = None,
    ) -> ResultStream:
        """Create a streaming URL where the rendered TTS can be retrieved."""
        if (engine_instance := get_engine_instance(self.hass, engine)) is None:
            raise HomeAssistantError(f"Provider {engine} not found")

        language, options = self.process_options(engine_instance, language, options)
        if use_file_cache is None:
            use_file_cache = self.use_file_cache

        extension = options.get(ATTR_PREFERRED_FORMAT, _DEFAULT_FORMAT)
        token = f"{secrets.token_urlsafe(16)}.{extension}"
        content, _ = mimetypes.guess_type(token)
        result_stream = ResultStream(
            token=token,
            extension=extension,
            content_type=content or "audio/mpeg",
            use_file_cache=use_file_cache,
            engine=engine,
            language=language,
            options=options,
            _manager=self,
        )
        self.token_to_stream[token] = result_stream

        if message is None:
            return result_stream

        cache_key = self._async_ensure_cached_in_memory(
            engine=engine,
            engine_instance=engine_instance,
            message=message,
            use_file_cache=use_file_cache,
            language=language,
            options=options,
        )
        result_stream.async_set_message_cache_key(cache_key)

        return result_stream

    @callback
    def async_cache_message_in_memory(
        self,
        engine: str,
        message: str,
        use_file_cache: bool | None = None,
        language: str | None = None,
        options: dict | None = None,
    ) -> str:
        """Make sure a message is cached in memory and returns cache key."""
        if (engine_instance := get_engine_instance(self.hass, engine)) is None:
            raise HomeAssistantError(f"Provider {engine} not found")

        language, options = self.process_options(engine_instance, language, options)
        if use_file_cache is None:
            use_file_cache = self.use_file_cache

        return self._async_ensure_cached_in_memory(
            engine=engine,
            engine_instance=engine_instance,
            message=message,
            use_file_cache=use_file_cache,
            language=language,
            options=options,
        )

    @callback
    def _async_ensure_cached_in_memory(
        self,
        engine: str,
        engine_instance: TextToSpeechEntity | Provider,
        message: str,
        use_file_cache: bool,
        language: str,
        options: dict,
    ) -> str:
        """Ensure a message is cached.

        Requires options, language to be processed.
        """
        options_key = _hash_options(options) if options else "-"
        msg_hash = hashlib.sha1(bytes(message, "utf-8")).hexdigest()
        cache_key = KEY_PATTERN.format(
            msg_hash, language.replace("_", "-"), options_key, engine
        ).lower()

        # Is speech already in memory
        if cache_key in self.mem_cache:
            return cache_key

        if use_file_cache and cache_key in self.file_cache:
            coro = self._async_load_file_to_mem(cache_key)
        else:
            coro = self._async_generate_tts_audio(
                engine_instance, cache_key, message, use_file_cache, language, options
            )

        task = self.hass.async_create_task(coro, eager_start=False)

        def handle_error(future: asyncio.Future) -> None:
            """Handle error."""
            if not (err := future.exception()):
                return
            # Truncate message so we don't flood the logs. Cutting off at 32 chars
            # but since we add 3 dots to truncated message, we cut off at 35.
            trunc_msg = message if len(message) < 35 else f"{message[0:32]}…"
            _LOGGER.error("Error generating audio for %s: %s", trunc_msg, err)
            self.mem_cache.pop(cache_key, None)

        task.add_done_callback(handle_error)

        self.mem_cache[cache_key] = {
            "extension": "",
            "voice": b"",
            "pending": task,
            "last_used": monotonic(),
        }
        return cache_key

    async def async_get_tts_audio(self, cache_key: str) -> tuple[str, bytes]:
        """Fetch TTS audio."""
        cached = self.mem_cache.get(cache_key)
        if cached is None:
            raise HomeAssistantError("Audio not cached")
        if pending := cached.get("pending"):
            await pending
            cached = self.mem_cache[cache_key]
        cached["last_used"] = monotonic()
        return cached["extension"], cached["voice"]

    async def _async_generate_tts_audio(
        self,
        engine_instance: TextToSpeechEntity | Provider,
        cache_key: str,
        message: str,
        cache_to_disk: bool,
        language: str,
        options: dict[str, Any],
    ) -> None:
        """Start loading of the TTS audio.

        This method is a coroutine.
        """
        options = dict(options or {})
        supported_options = engine_instance.supported_options or []

        # Extract preferred format options.
        #
        # These options are used by Assist pipelines, etc. to get a format that
        # the voice satellite will support.
        #
        # The TTS system ideally supports options directly so we won't have
        # to convert with ffmpeg later. If not, we pop the options here and
        # perform the conversation after receiving the audio.
        if ATTR_PREFERRED_FORMAT in supported_options:
            final_extension = options.get(ATTR_PREFERRED_FORMAT, _DEFAULT_FORMAT)
        else:
            final_extension = options.pop(ATTR_PREFERRED_FORMAT, _DEFAULT_FORMAT)

        if ATTR_PREFERRED_SAMPLE_RATE in supported_options:
            sample_rate = options.get(ATTR_PREFERRED_SAMPLE_RATE)
        else:
            sample_rate = options.pop(ATTR_PREFERRED_SAMPLE_RATE, None)

        if sample_rate is not None:
            sample_rate = int(sample_rate)

        if ATTR_PREFERRED_SAMPLE_CHANNELS in supported_options:
            sample_channels = options.get(ATTR_PREFERRED_SAMPLE_CHANNELS)
        else:
            sample_channels = options.pop(ATTR_PREFERRED_SAMPLE_CHANNELS, None)

        if sample_channels is not None:
            sample_channels = int(sample_channels)

        if ATTR_PREFERRED_SAMPLE_BYTES in supported_options:
            sample_bytes = options.get(ATTR_PREFERRED_SAMPLE_BYTES)
        else:
            sample_bytes = options.pop(ATTR_PREFERRED_SAMPLE_BYTES, None)

        if sample_bytes is not None:
            sample_bytes = int(sample_bytes)

        if engine_instance.name is None or engine_instance.name is UNDEFINED:
            raise HomeAssistantError("TTS engine name is not set.")

        if isinstance(engine_instance, Provider):
            extension, data = await engine_instance.async_get_tts_audio(
                message, language, options
            )
        else:
            extension, data = await engine_instance.internal_async_get_tts_audio(
                message, language, options
            )

        if data is None or extension is None:
            raise HomeAssistantError(
                f"No TTS from {engine_instance.name} for '{message}'"
            )

        # Only convert if we have a preferred format different than the
        # expected format from the TTS system, or if a specific sample
        # rate/format/channel count is requested.
        needs_conversion = (
            (final_extension != extension)
            or (sample_rate is not None)
            or (sample_channels is not None)
            or (sample_bytes is not None)
        )

        if needs_conversion:
            data = await async_convert_audio(
                self.hass,
                extension,
                data,
                to_extension=final_extension,
                to_sample_rate=sample_rate,
                to_sample_channels=sample_channels,
                to_sample_bytes=sample_bytes,
            )

        # Create file infos
        filename = f"{cache_key}.{final_extension}".lower()

        # Validate filename
        if not _RE_VOICE_FILE.match(filename) and not _RE_LEGACY_VOICE_FILE.match(
            filename
        ):
            raise HomeAssistantError(
                f"TTS filename '{filename}' from {engine_instance.name} is invalid!"
            )

        # Save to memory
        if final_extension == "mp3":
            data = self.write_tags(
                filename, data, engine_instance.name, message, language, options
            )

        self._async_store_to_memcache(cache_key, final_extension, data)

        if not cache_to_disk:
            return

        voice_file = os.path.join(self.cache_dir, filename)

        def save_speech() -> None:
            """Store speech to filesystem."""
            with open(voice_file, "wb") as speech:
                speech.write(data)

        # Don't await, we're going to do this in the background
        task = self.hass.async_add_executor_job(save_speech)

        def write_done(future: asyncio.Future) -> None:
            """Write is done task."""
            if err := future.exception():
                _LOGGER.error("Can't write %s: %s", filename, err)
            else:
                self.file_cache[cache_key] = filename

        task.add_done_callback(write_done)

    async def _async_load_file_to_mem(self, cache_key: str) -> None:
        """Load voice from file cache into memory.

        This method is a coroutine.
        """
        if not (filename := self.file_cache.get(cache_key)):
            raise HomeAssistantError(f"Key {cache_key} not in file cache!")

        voice_file = os.path.join(self.cache_dir, filename)

        def load_speech() -> bytes:
            """Load a speech from filesystem."""
            with open(voice_file, "rb") as speech:
                return speech.read()

        try:
            data = await self.hass.async_add_executor_job(load_speech)
        except OSError as err:
            del self.file_cache[cache_key]
            raise HomeAssistantError(f"Can't read {voice_file}") from err

        extension = os.path.splitext(filename)[1][1:]

        self._async_store_to_memcache(cache_key, extension, data)

    @callback
    def _async_store_to_memcache(
        self, cache_key: str, extension: str, data: bytes
    ) -> None:
        """Store data to memcache and set timer to remove it."""
        self.mem_cache[cache_key] = {
            "extension": extension,
            "voice": data,
            "pending": None,
            "last_used": monotonic(),
        }
        self.memcache_cleanup.schedule()

    @staticmethod
    def write_tags(
        filename: str,
        data: bytes,
        engine_name: str,
        message: str,
        language: str,
        options: dict | None,
    ) -> bytes:
        """Write ID3 tags to file.

        Async friendly.
        """

        data_bytes = io.BytesIO(data)
        data_bytes.name = filename
        data_bytes.seek(0)

        album = engine_name
        artist = language

        if options is not None and (voice := options.get("voice")) is not None:
            artist = voice

        try:
            tts_file = mutagen.File(data_bytes)
            if tts_file is not None:
                if not tts_file.tags:
                    tts_file.add_tags()
                if isinstance(tts_file.tags, ID3):
                    tts_file["artist"] = ID3Text(
                        encoding=3,
                        text=artist,  # type: ignore[no-untyped-call]
                    )
                    tts_file["album"] = ID3Text(
                        encoding=3,
                        text=album,  # type: ignore[no-untyped-call]
                    )
                    tts_file["title"] = ID3Text(
                        encoding=3,
                        text=message,  # type: ignore[no-untyped-call]
                    )
                else:
                    tts_file["artist"] = artist
                    tts_file["album"] = album
                    tts_file["title"] = message
                tts_file.save(data_bytes)
        except mutagen.MutagenError as err:
            _LOGGER.error("ID3 tag error: %s", err)

        return data_bytes.getvalue()


def _init_tts_cache_dir(hass: HomeAssistant, cache_dir: str) -> str:
    """Init cache folder."""
    if not os.path.isabs(cache_dir):
        cache_dir = hass.config.path(cache_dir)
    if not os.path.isdir(cache_dir):
        _LOGGER.info("Create cache dir %s", cache_dir)
        os.mkdir(cache_dir)
    return cache_dir


def _get_cache_files(cache_dir: str) -> dict[str, str]:
    """Return a dict of given engine files."""
    cache = {}

    folder_data = os.listdir(cache_dir)
    for file_data in folder_data:
        if (record := _RE_VOICE_FILE.match(file_data)) or (
            record := _RE_LEGACY_VOICE_FILE.match(file_data)
        ):
            key = KEY_PATTERN.format(
                record.group(1), record.group(2), record.group(3), record.group(4)
            )
            cache[key.lower()] = file_data.lower()
    return cache


class TextToSpeechUrlView(HomeAssistantView):
    """TTS view to get a url to a generated speech file."""

    requires_auth = True
    url = "/api/tts_get_url"
    name = "api:tts:geturl"

    def __init__(self, manager: SpeechManager) -> None:
        """Initialize a tts view."""
        self.manager = manager

    async def post(self, request: web.Request) -> web.Response:
        """Generate speech and provide url."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTPStatus.BAD_REQUEST)
        if (not data.get("engine_id") and not data.get(ATTR_PLATFORM)) or not data.get(
            ATTR_MESSAGE
        ):
            return self.json_message(
                "Must specify platform and message", HTTPStatus.BAD_REQUEST
            )

        engine = data.get("engine_id") or data[ATTR_PLATFORM]
        message = data[ATTR_MESSAGE]
        use_file_cache = data.get(ATTR_CACHE)
        language = data.get(ATTR_LANGUAGE)
        options = data.get(ATTR_OPTIONS)

        try:
            stream = self.manager.async_create_result_stream(
                engine,
                message,
                use_file_cache=use_file_cache,
                language=language,
                options=options,
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error on init tts: %s", err)
            return self.json({"error": err}, HTTPStatus.BAD_REQUEST)

        base = get_url(self.manager.hass)
        url = base + stream.url

        return self.json({"url": url, "path": stream.url})


class TextToSpeechView(HomeAssistantView):
    """TTS view to serve a speech audio."""

    requires_auth = False
    url = "/api/tts_proxy/{token}"
    name = "api:tts_speech"

    def __init__(self, manager: SpeechManager) -> None:
        """Initialize a tts view."""
        self.manager = manager

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Start a get request."""
        stream = self.manager.token_to_stream.get(token)

        if stream is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        response: web.StreamResponse | None = None
        try:
            async for data in stream.async_stream_result():
                if response is None:
                    response = web.StreamResponse()
                    response.content_type = stream.content_type
                    await response.prepare(request)

                await response.write(data)
        # pylint: disable=broad-except
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error streaming tts: %s", err)

        # Empty result or exception happened
        if response is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        await response.write_eof()
        return response


@websocket_api.websocket_command(
    {
        "type": "tts/engine/list",
        vol.Optional("country"): str,
        vol.Optional("language"): str,
    }
)
@callback
def websocket_list_engines(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List text to speech engines and, optionally, if they support a given language."""
    country = msg.get("country")
    language = msg.get("language")
    providers = []
    provider_info: dict[str, Any]
    entity_domains: set[str] = set()

    for entity in hass.data[DATA_COMPONENT].entities:
        provider_info = {
            "engine_id": entity.entity_id,
            "supported_languages": entity.supported_languages,
        }
        if language:
            provider_info["supported_languages"] = language_util.matches(
                language, entity.supported_languages, country
            )
        providers.append(provider_info)
        if entity.platform:
            entity_domains.add(entity.platform.platform_name)
    for engine_id, provider in hass.data[DATA_TTS_MANAGER].providers.items():
        provider_info = {
            "engine_id": engine_id,
            "name": provider.name,
            "supported_languages": provider.supported_languages,
        }
        if language:
            provider_info["supported_languages"] = language_util.matches(
                language, provider.supported_languages, country
            )
        if engine_id in entity_domains:
            provider_info["deprecated"] = True
        providers.append(provider_info)

    connection.send_message(
        websocket_api.result_message(msg["id"], {"providers": providers})
    )


@websocket_api.websocket_command(
    {
        "type": "tts/engine/get",
        vol.Required("engine_id"): str,
    }
)
@callback
def websocket_get_engine(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get text to speech engine info."""
    engine_id = msg["engine_id"]
    provider_info: dict[str, Any]

    provider: TextToSpeechEntity | Provider | None = next(
        (
            entity
            for entity in hass.data[DATA_COMPONENT].entities
            if entity.entity_id == engine_id
        ),
        None,
    )
    if not provider:
        provider = hass.data[DATA_TTS_MANAGER].providers.get(engine_id)

    if not provider:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"tts engine {engine_id} not found",
        )
        return

    provider_info = {
        "engine_id": engine_id,
        "supported_languages": provider.supported_languages,
    }
    if isinstance(provider, Provider):
        provider_info["name"] = provider.name

    connection.send_message(
        websocket_api.result_message(msg["id"], {"provider": provider_info})
    )


@websocket_api.websocket_command(
    {
        "type": "tts/engine/voices",
        vol.Required("engine_id"): str,
        vol.Required("language"): str,
    }
)
@callback
def websocket_list_engine_voices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List voices for a given language."""
    engine_id = msg["engine_id"]
    language = msg["language"]

    engine_instance = get_engine_instance(hass, engine_id)

    if not engine_instance:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"tts engine {engine_id} not found",
        )
        return

    voices = {"voices": engine_instance.async_get_supported_voices(language)}

    connection.send_message(websocket_api.result_message(msg["id"], voices))
