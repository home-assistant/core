"""Provide functionality for TTS."""
from __future__ import annotations

import asyncio
import functools as ft
import hashlib
from http import HTTPStatus
import io
import logging
import mimetypes
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, TypedDict, cast

from aiohttp import web
import mutagen
from mutagen.id3 import ID3, TextFrame as ID3Text
import voluptuous as vol
import yarl

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DESCRIPTION,
    CONF_NAME,
    CONF_PLATFORM,
    PLATFORM_FORMAT,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import get_url
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util.network import normalize_url
from homeassistant.util.yaml import load_yaml

from .const import DOMAIN
from .media_source import generate_media_source_id, media_source_id_to_kwargs

_LOGGER = logging.getLogger(__name__)

TtsAudioType = tuple[str | None, bytes | None]

ATTR_CACHE = "cache"
ATTR_LANGUAGE = "language"
ATTR_MESSAGE = "message"
ATTR_OPTIONS = "options"
ATTR_PLATFORM = "platform"

BASE_URL_KEY = "tts_base_url"

CONF_BASE_URL = "base_url"
CONF_CACHE = "cache"
CONF_CACHE_DIR = "cache_dir"
CONF_LANG = "language"
CONF_SERVICE_NAME = "service_name"
CONF_TIME_MEMORY = "time_memory"

CONF_FIELDS = "fields"

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300

SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_SAY = "say"

_RE_VOICE_FILE = re.compile(r"([a-f0-9]{40})_([^_]+)_([^_]+)_([a-z_]+)\.[a-z0-9]{3,4}")
KEY_PATTERN = "{0}_{1}_{2}_{3}"


def _deprecated_platform(value: str) -> str:
    """Validate if platform is deprecated."""
    if value == "google":
        raise vol.Invalid(
            "google tts service has been renamed to google_translate,"
            " please update your configuration."
        )
    return value


def valid_base_url(value: str) -> str:
    """Validate base url, return value."""
    url = yarl.URL(cv.url(value))

    if url.path != "/":
        raise vol.Invalid("Path should be empty")

    return normalize_url(value)


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): vol.All(cv.string, _deprecated_platform),
        vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
        vol.Optional(CONF_CACHE_DIR, default=DEFAULT_CACHE_DIR): cv.string,
        vol.Optional(CONF_TIME_MEMORY, default=DEFAULT_TIME_MEMORY): vol.All(
            vol.Coerce(int), vol.Range(min=60, max=57600)
        ),
        vol.Optional(CONF_BASE_URL): valid_base_url,
        vol.Optional(CONF_SERVICE_NAME): cv.string,
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)

SCHEMA_SERVICE_SAY = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_CACHE): cv.boolean,
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_OPTIONS): dict,
    }
)

SCHEMA_SERVICE_CLEAR_CACHE = vol.Schema({})


class TTSCache(TypedDict):
    """Cached TTS file."""

    filename: str
    voice: bytes


async def async_get_media_source_audio(
    hass: HomeAssistant,
    media_source_id: str,
) -> tuple[str, bytes]:
    """Get TTS audio as extension, data."""
    manager: SpeechManager = hass.data[DOMAIN]
    return await manager.async_get_tts_audio(
        **media_source_id_to_kwargs(media_source_id),
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up TTS."""
    tts = SpeechManager(hass)

    try:
        conf = config[DOMAIN][0] if config.get(DOMAIN, []) else {}
        use_cache = conf.get(CONF_CACHE, DEFAULT_CACHE)
        cache_dir = conf.get(CONF_CACHE_DIR, DEFAULT_CACHE_DIR)
        time_memory = conf.get(CONF_TIME_MEMORY, DEFAULT_TIME_MEMORY)
        base_url = conf.get(CONF_BASE_URL)
        if base_url is not None:
            _LOGGER.warning(
                "TTS base_url option is deprecated. Configure internal/external URL"
                " instead"
            )
        hass.data[BASE_URL_KEY] = base_url

        await tts.async_init_cache(use_cache, cache_dir, time_memory, base_url)
    except (HomeAssistantError, KeyError):
        _LOGGER.exception("Error on cache init")
        return False

    hass.data[DOMAIN] = tts
    hass.http.register_view(TextToSpeechView(tts))
    hass.http.register_view(TextToSpeechUrlView(tts))

    # Load service descriptions from tts/services.yaml
    services_yaml = Path(__file__).parent / "services.yaml"
    services_dict = cast(
        dict, await hass.async_add_executor_job(load_yaml, str(services_yaml))
    )

    async def async_setup_platform(
        p_type: str,
        p_config: ConfigType | None = None,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up a TTS platform."""
        if p_config is None:
            p_config = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            if hasattr(platform, "async_get_engine"):
                provider = await platform.async_get_engine(
                    hass, p_config, discovery_info
                )
            else:
                provider = await hass.async_add_executor_job(
                    platform.get_engine, hass, p_config, discovery_info
                )

            if provider is None:
                _LOGGER.error("Error setting up platform %s", p_type)
                return

            tts.async_register_engine(p_type, provider, p_config)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform: %s", p_type)
            return

        async def async_say_handle(service: ServiceCall) -> None:
            """Service handle for say."""
            entity_ids = service.data[ATTR_ENTITY_ID]

            await hass.services.async_call(
                DOMAIN_MP,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: entity_ids,
                    ATTR_MEDIA_CONTENT_ID: generate_media_source_id(
                        hass,
                        engine=p_type,
                        message=service.data[ATTR_MESSAGE],
                        language=service.data.get(ATTR_LANGUAGE),
                        options=service.data.get(ATTR_OPTIONS),
                        cache=service.data.get(ATTR_CACHE),
                    ),
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                    ATTR_MEDIA_ANNOUNCE: True,
                },
                blocking=True,
                context=service.context,
            )

        service_name = p_config.get(CONF_SERVICE_NAME, f"{p_type}_{SERVICE_SAY}")
        hass.services.async_register(
            DOMAIN, service_name, async_say_handle, schema=SCHEMA_SERVICE_SAY
        )

        # Register the service description
        service_desc = {
            CONF_NAME: f"Say a TTS message with {p_type}",
            CONF_DESCRIPTION: (
                f"Say something using text-to-speech on a media player with {p_type}."
            ),
            CONF_FIELDS: services_dict[SERVICE_SAY][CONF_FIELDS],
        }
        async_set_service_schema(hass, DOMAIN, service_name, service_desc)

    setup_tasks = [
        asyncio.create_task(async_setup_platform(p_type, p_config))
        for p_type, p_config in config_per_platform(config, DOMAIN)
        if p_type is not None
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(
        platform: str, info: dict[str, Any] | None
    ) -> None:
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    async def async_clear_cache_handle(service: ServiceCall) -> None:
        """Handle clear cache service call."""
        await tts.async_clear_cache()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        async_clear_cache_handle,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )

    return True


def _hash_options(options: dict) -> str:
    """Hashes an options dictionary."""
    opts_hash = hashlib.blake2s(digest_size=5)
    for key, value in sorted(options.items()):
        opts_hash.update(str(key).encode())
        opts_hash.update(str(value).encode())

    return opts_hash.hexdigest()


class SpeechManager:
    """Representation of a speech store."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a speech store."""
        self.hass = hass
        self.providers: dict[str, Provider] = {}

        self.use_cache = DEFAULT_CACHE
        self.cache_dir = DEFAULT_CACHE_DIR
        self.time_memory = DEFAULT_TIME_MEMORY
        self.base_url: str | None = None
        self.file_cache: dict[str, str] = {}
        self.mem_cache: dict[str, TTSCache] = {}

    async def async_init_cache(
        self, use_cache: bool, cache_dir: str, time_memory: int, base_url: str | None
    ) -> None:
        """Init config folder and load file cache."""
        self.use_cache = use_cache
        self.time_memory = time_memory
        self.base_url = base_url

        try:
            self.cache_dir = await self.hass.async_add_executor_job(
                _init_tts_cache_dir, self.hass, cache_dir
            )
        except OSError as err:
            raise HomeAssistantError(f"Can't init cache dir {err}") from err

        try:
            cache_files = await self.hass.async_add_executor_job(
                _get_cache_files, self.cache_dir
            )
        except OSError as err:
            raise HomeAssistantError(f"Can't read cache dir {err}") from err

        if cache_files:
            self.file_cache.update(cache_files)

    async def async_clear_cache(self) -> None:
        """Read file cache and delete files."""
        self.mem_cache = {}

        def remove_files() -> None:
            """Remove files from filesystem."""
            for filename in self.file_cache.values():
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError as err:
                    _LOGGER.warning("Can't remove cache file '%s': %s", filename, err)

        await self.hass.async_add_executor_job(remove_files)
        self.file_cache = {}

    @callback
    def async_register_engine(
        self, engine: str, provider: Provider, config: ConfigType
    ) -> None:
        """Register a TTS provider."""
        provider.hass = self.hass
        if provider.name is None:
            provider.name = engine
        self.providers[engine] = provider

        self.hass.config.components.add(
            PLATFORM_FORMAT.format(domain=engine, platform=DOMAIN)
        )

    @callback
    def process_options(
        self,
        engine: str,
        language: str | None = None,
        options: dict | None = None,
    ) -> tuple[str, dict | None]:
        """Validate and process options."""
        if (provider := self.providers.get(engine)) is None:
            raise HomeAssistantError(f"Provider {engine} not found")

        # Languages
        language = language or provider.default_language
        if (
            language is None
            or provider.supported_languages is None
            or language not in provider.supported_languages
        ):
            raise HomeAssistantError(f"Not supported language {language}")

        # Options
        if provider.default_options and options:
            merged_options = provider.default_options.copy()
            merged_options.update(options)
            options = merged_options
        options = options or provider.default_options

        if options is not None:
            supported_options = provider.supported_options or []
            invalid_opts = [
                opt_name for opt_name in options if opt_name not in supported_options
            ]
            if invalid_opts:
                raise HomeAssistantError(f"Invalid options found: {invalid_opts}")

        return language, options

    async def async_get_url_path(
        self,
        engine: str,
        message: str,
        cache: bool | None = None,
        language: str | None = None,
        options: dict | None = None,
    ) -> str:
        """Get URL for play message.

        This method is a coroutine.
        """
        language, options = self.process_options(engine, language, options)
        cache_key = self._generate_cache_key(message, language, options, engine)
        use_cache = cache if cache is not None else self.use_cache

        # Is speech already in memory
        if cache_key in self.mem_cache:
            filename = self.mem_cache[cache_key]["filename"]
        # Is file store in file cache
        elif use_cache and cache_key in self.file_cache:
            filename = self.file_cache[cache_key]
            self.hass.async_create_task(self._async_file_to_mem(cache_key))
        # Load speech from provider into memory
        else:
            filename = await self._async_get_tts_audio(
                engine,
                cache_key,
                message,
                use_cache,
                language,
                options,
            )

        return f"/api/tts_proxy/{filename}"

    async def async_get_tts_audio(
        self,
        engine: str,
        message: str,
        cache: bool | None = None,
        language: str | None = None,
        options: dict | None = None,
    ) -> tuple[str, bytes]:
        """Fetch TTS audio."""
        language, options = self.process_options(engine, language, options)
        cache_key = self._generate_cache_key(message, language, options, engine)
        use_cache = cache if cache is not None else self.use_cache

        # If we have the file, load it into memory if necessary
        if cache_key not in self.mem_cache:
            if use_cache and cache_key in self.file_cache:
                await self._async_file_to_mem(cache_key)
            else:
                await self._async_get_tts_audio(
                    engine, cache_key, message, use_cache, language, options
                )

        extension = os.path.splitext(self.mem_cache[cache_key]["filename"])[1][1:]
        data = self.mem_cache[cache_key]["voice"]
        return extension, data

    @callback
    def _generate_cache_key(
        self,
        message: str,
        language: str,
        options: dict | None,
        engine: str,
    ) -> str:
        """Generate a cache key for a message."""
        options_key = _hash_options(options) if options else "-"
        msg_hash = hashlib.sha1(bytes(message, "utf-8")).hexdigest()
        return KEY_PATTERN.format(
            msg_hash, language.replace("_", "-"), options_key, engine
        ).lower()

    async def _async_get_tts_audio(
        self,
        engine: str,
        cache_key: str,
        message: str,
        cache: bool,
        language: str,
        options: dict | None,
    ) -> str:
        """Receive TTS, store for view in cache and return filename.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        extension, data = await provider.async_get_tts_audio(message, language, options)

        if data is None or extension is None:
            raise HomeAssistantError(f"No TTS from {engine} for '{message}'")

        # Create file infos
        filename = f"{cache_key}.{extension}".lower()

        # Validate filename
        if not _RE_VOICE_FILE.match(filename):
            raise HomeAssistantError(
                f"TTS filename '{filename}' from {engine} is invalid!"
            )

        # Save to memory
        data = self.write_tags(filename, data, provider, message, language, options)
        self._async_store_to_memcache(cache_key, filename, data)

        if cache:
            self.hass.async_create_task(
                self._async_save_tts_audio(cache_key, filename, data)
            )

        return filename

    async def _async_save_tts_audio(
        self, cache_key: str, filename: str, data: bytes
    ) -> None:
        """Store voice data to file and file_cache.

        This method is a coroutine.
        """
        voice_file = os.path.join(self.cache_dir, filename)

        def save_speech() -> None:
            """Store speech to filesystem."""
            with open(voice_file, "wb") as speech:
                speech.write(data)

        try:
            await self.hass.async_add_executor_job(save_speech)
            self.file_cache[cache_key] = filename
        except OSError as err:
            _LOGGER.error("Can't write %s: %s", filename, err)

    async def _async_file_to_mem(self, cache_key: str) -> None:
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

        self._async_store_to_memcache(cache_key, filename, data)

    @callback
    def _async_store_to_memcache(
        self, cache_key: str, filename: str, data: bytes
    ) -> None:
        """Store data to memcache and set timer to remove it."""
        self.mem_cache[cache_key] = {"filename": filename, "voice": data}

        @callback
        def async_remove_from_mem() -> None:
            """Cleanup memcache."""
            self.mem_cache.pop(cache_key, None)

        self.hass.loop.call_later(self.time_memory, async_remove_from_mem)

    async def async_read_tts(self, filename: str) -> tuple[str | None, bytes]:
        """Read a voice file and return binary.

        This method is a coroutine.
        """
        if not (record := _RE_VOICE_FILE.match(filename.lower())):
            raise HomeAssistantError("Wrong tts file format!")

        cache_key = KEY_PATTERN.format(
            record.group(1), record.group(2), record.group(3), record.group(4)
        )

        if cache_key not in self.mem_cache:
            if cache_key not in self.file_cache:
                raise HomeAssistantError(f"{cache_key} not in cache!")
            await self._async_file_to_mem(cache_key)

        content, _ = mimetypes.guess_type(filename)
        return content, self.mem_cache[cache_key]["voice"]

    @staticmethod
    def write_tags(
        filename: str,
        data: bytes,
        provider: Provider,
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

        album = provider.name
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


class Provider:
    """Represent a single TTS provider."""

    hass: HomeAssistant | None = None
    name: str | None = None

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return None

    @property
    def supported_languages(self) -> list[str] | None:
        """Return a list of supported languages."""
        return None

    @property
    def supported_options(self) -> list[str] | None:
        """Return a list of supported options like voice, emotions."""
        return None

    @property
    def default_options(self) -> dict[str, Any] | None:
        """Return a dict include default options."""
        return None

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load tts audio file from provider."""
        raise NotImplementedError()

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load tts audio file from provider.

        Return a tuple of file extension and data as bytes.
        """
        if TYPE_CHECKING:
            assert self.hass
        return await self.hass.async_add_executor_job(
            ft.partial(self.get_tts_audio, message, language, options=options)
        )


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
        if record := _RE_VOICE_FILE.match(file_data):
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

    def __init__(self, tts: SpeechManager) -> None:
        """Initialize a tts view."""
        self.tts = tts

    async def post(self, request: web.Request) -> web.Response:
        """Generate speech and provide url."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTPStatus.BAD_REQUEST)
        if not data.get(ATTR_PLATFORM) and data.get(ATTR_MESSAGE):
            return self.json_message(
                "Must specify platform and message", HTTPStatus.BAD_REQUEST
            )

        p_type = data[ATTR_PLATFORM]
        message = data[ATTR_MESSAGE]
        cache = data.get(ATTR_CACHE)
        language = data.get(ATTR_LANGUAGE)
        options = data.get(ATTR_OPTIONS)

        try:
            path = await self.tts.async_get_url_path(
                p_type, message, cache=cache, language=language, options=options
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error on init tts: %s", err)
            return self.json({"error": err}, HTTPStatus.BAD_REQUEST)

        base = self.tts.base_url or get_url(self.tts.hass)
        url = base + path

        return self.json({"url": url, "path": path})


class TextToSpeechView(HomeAssistantView):
    """TTS view to serve a speech audio."""

    requires_auth = False
    url = "/api/tts_proxy/{filename}"
    name = "api:tts_speech"

    def __init__(self, tts: SpeechManager) -> None:
        """Initialize a tts view."""
        self.tts = tts

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Start a get request."""
        try:
            content, data = await self.tts.async_read_tts(filename)
        except HomeAssistantError as err:
            _LOGGER.error("Error on load tts: %s", err)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        return web.Response(body=data, content_type=content)


def get_base_url(hass: HomeAssistant) -> str:
    """Get base URL."""
    return hass.data[BASE_URL_KEY] or get_url(hass)
