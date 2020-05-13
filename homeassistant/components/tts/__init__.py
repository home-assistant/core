"""Provide functionality for TTS."""
import asyncio
import ctypes
import functools as ft
import hashlib
import io
import logging
import mimetypes
import os
import re
from typing import Optional

from aiohttp import web
import mutagen
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_OK,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_prepare_setup_platform

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_CACHE = "cache"
ATTR_LANGUAGE = "language"
ATTR_MESSAGE = "message"
ATTR_OPTIONS = "options"
ATTR_PLATFORM = "platform"

CONF_BASE_URL = "base_url"
CONF_CACHE = "cache"
CONF_CACHE_DIR = "cache_dir"
CONF_LANG = "language"
CONF_SERVICE_NAME = "service_name"
CONF_TIME_MEMORY = "time_memory"

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300
DOMAIN = "tts"

MEM_CACHE_FILENAME = "filename"
MEM_CACHE_VOICE = "voice"

SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_SAY = "say"

_RE_VOICE_FILE = re.compile(r"([a-f0-9]{40})_([^_]+)_([^_]+)_([a-z_]+)\.[a-z0-9]{3,4}")
KEY_PATTERN = "{0}_{1}_{2}_{3}"


def _deprecated_platform(value):
    """Validate if platform is deprecated."""
    if value == "google":
        raise vol.Invalid(
            "google tts service has been renamed to google_translate,"
            " please update your configuration."
        )
    return value


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): vol.All(cv.string, _deprecated_platform),
        vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
        vol.Optional(CONF_CACHE_DIR, default=DEFAULT_CACHE_DIR): cv.string,
        vol.Optional(CONF_TIME_MEMORY, default=DEFAULT_TIME_MEMORY): vol.All(
            vol.Coerce(int), vol.Range(min=60, max=57600)
        ),
        vol.Optional(CONF_BASE_URL): cv.string,
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


async def async_setup(hass, config):
    """Set up TTS."""
    tts = SpeechManager(hass)

    try:
        conf = config[DOMAIN][0] if config.get(DOMAIN, []) else {}
        use_cache = conf.get(CONF_CACHE, DEFAULT_CACHE)
        cache_dir = conf.get(CONF_CACHE_DIR, DEFAULT_CACHE_DIR)
        time_memory = conf.get(CONF_TIME_MEMORY, DEFAULT_TIME_MEMORY)
        base_url = conf.get(CONF_BASE_URL) or get_url(hass)

        await tts.async_init_cache(use_cache, cache_dir, time_memory, base_url)
    except (HomeAssistantError, KeyError) as err:
        _LOGGER.error("Error on cache init %s", err)
        return False

    hass.http.register_view(TextToSpeechView(tts))
    hass.http.register_view(TextToSpeechUrlView(tts))

    async def async_setup_platform(p_type, p_config=None, discovery_info=None):
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

        async def async_say_handle(service):
            """Service handle for say."""
            entity_ids = service.data[ATTR_ENTITY_ID]
            message = service.data.get(ATTR_MESSAGE)
            cache = service.data.get(ATTR_CACHE)
            language = service.data.get(ATTR_LANGUAGE)
            options = service.data.get(ATTR_OPTIONS)

            try:
                url = await tts.async_get_url(
                    p_type, message, cache=cache, language=language, options=options
                )
            except HomeAssistantError as err:
                _LOGGER.error("Error on init TTS: %s", err)
                return

            data = {
                ATTR_MEDIA_CONTENT_ID: url,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_ENTITY_ID: entity_ids,
            }

            await hass.services.async_call(
                DOMAIN_MP, SERVICE_PLAY_MEDIA, data, blocking=True
            )

        service_name = p_config.get(CONF_SERVICE_NAME, f"{p_type}_{SERVICE_SAY}")
        hass.services.async_register(
            DOMAIN, service_name, async_say_handle, schema=SCHEMA_SERVICE_SAY
        )

    setup_tasks = [
        async_setup_platform(p_type, p_config)
        for p_type, p_config in config_per_platform(config, DOMAIN)
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    async def async_clear_cache_handle(service):
        """Handle clear cache service call."""
        await tts.async_clear_cache()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        async_clear_cache_handle,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )

    return True


class SpeechManager:
    """Representation of a speech store."""

    def __init__(self, hass):
        """Initialize a speech store."""
        self.hass = hass
        self.providers = {}

        self.use_cache = DEFAULT_CACHE
        self.cache_dir = DEFAULT_CACHE_DIR
        self.time_memory = DEFAULT_TIME_MEMORY
        self.base_url = None
        self.file_cache = {}
        self.mem_cache = {}

    async def async_init_cache(self, use_cache, cache_dir, time_memory, base_url):
        """Init config folder and load file cache."""
        self.use_cache = use_cache
        self.time_memory = time_memory
        self.base_url = base_url

        try:
            self.cache_dir = await self.hass.async_add_executor_job(
                _init_tts_cache_dir, self.hass, cache_dir
            )
        except OSError as err:
            raise HomeAssistantError(f"Can't init cache dir {err}")

        try:
            cache_files = await self.hass.async_add_executor_job(
                _get_cache_files, self.cache_dir
            )
        except OSError as err:
            raise HomeAssistantError(f"Can't read cache dir {err}")

        if cache_files:
            self.file_cache.update(cache_files)

    async def async_clear_cache(self):
        """Read file cache and delete files."""
        self.mem_cache = {}

        def remove_files():
            """Remove files from filesystem."""
            for filename in self.file_cache.values():
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError as err:
                    _LOGGER.warning("Can't remove cache file '%s': %s", filename, err)

        await self.hass.async_add_executor_job(remove_files)
        self.file_cache = {}

    @callback
    def async_register_engine(self, engine, provider, config):
        """Register a TTS provider."""
        provider.hass = self.hass
        if provider.name is None:
            provider.name = engine
        self.providers[engine] = provider

    async def async_get_url(
        self, engine, message, cache=None, language=None, options=None
    ):
        """Get URL for play message.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        msg_hash = hashlib.sha1(bytes(message, "utf-8")).hexdigest()
        use_cache = cache if cache is not None else self.use_cache

        # Languages
        language = language or provider.default_language
        if language is None or language not in provider.supported_languages:
            raise HomeAssistantError(f"Not supported language {language}")

        # Options
        if provider.default_options and options:
            merged_options = provider.default_options.copy()
            merged_options.update(options)
            options = merged_options
        options = options or provider.default_options

        if options is not None:
            invalid_opts = [
                opt_name
                for opt_name in options.keys()
                if opt_name not in (provider.supported_options or [])
            ]
            if invalid_opts:
                raise HomeAssistantError(f"Invalid options found: {invalid_opts}")
            options_key = ctypes.c_size_t(hash(frozenset(options))).value
        else:
            options_key = "-"

        key = KEY_PATTERN.format(msg_hash, language, options_key, engine).lower()

        # Is speech already in memory
        if key in self.mem_cache:
            filename = self.mem_cache[key][MEM_CACHE_FILENAME]
        # Is file store in file cache
        elif use_cache and key in self.file_cache:
            filename = self.file_cache[key]
            self.hass.async_create_task(self.async_file_to_mem(key))
        # Load speech from provider into memory
        else:
            filename = await self.async_get_tts_audio(
                engine, key, message, use_cache, language, options
            )

        return f"{self.base_url}/api/tts_proxy/{filename}"

    async def async_get_tts_audio(self, engine, key, message, cache, language, options):
        """Receive TTS and store for view in cache.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        extension, data = await provider.async_get_tts_audio(message, language, options)

        if data is None or extension is None:
            raise HomeAssistantError(f"No TTS from {engine} for '{message}'")

        # Create file infos
        filename = f"{key}.{extension}".lower()

        data = self.write_tags(filename, data, provider, message, language, options)

        # Save to memory
        self._async_store_to_memcache(key, filename, data)

        if cache:
            self.hass.async_create_task(self.async_save_tts_audio(key, filename, data))

        return filename

    async def async_save_tts_audio(self, key, filename, data):
        """Store voice data to file and file_cache.

        This method is a coroutine.
        """
        voice_file = os.path.join(self.cache_dir, filename)

        def save_speech():
            """Store speech to filesystem."""
            with open(voice_file, "wb") as speech:
                speech.write(data)

        try:
            await self.hass.async_add_executor_job(save_speech)
            self.file_cache[key] = filename
        except OSError as err:
            _LOGGER.error("Can't write %s: %s", filename, err)

    async def async_file_to_mem(self, key):
        """Load voice from file cache into memory.

        This method is a coroutine.
        """
        filename = self.file_cache.get(key)
        if not filename:
            raise HomeAssistantError(f"Key {key} not in file cache!")

        voice_file = os.path.join(self.cache_dir, filename)

        def load_speech():
            """Load a speech from filesystem."""
            with open(voice_file, "rb") as speech:
                return speech.read()

        try:
            data = await self.hass.async_add_executor_job(load_speech)
        except OSError:
            del self.file_cache[key]
            raise HomeAssistantError(f"Can't read {voice_file}")

        self._async_store_to_memcache(key, filename, data)

    @callback
    def _async_store_to_memcache(self, key, filename, data):
        """Store data to memcache and set timer to remove it."""
        self.mem_cache[key] = {MEM_CACHE_FILENAME: filename, MEM_CACHE_VOICE: data}

        @callback
        def async_remove_from_mem():
            """Cleanup memcache."""
            self.mem_cache.pop(key)

        self.hass.loop.call_later(self.time_memory, async_remove_from_mem)

    async def async_read_tts(self, filename):
        """Read a voice file and return binary.

        This method is a coroutine.
        """
        record = _RE_VOICE_FILE.match(filename.lower())
        if not record:
            raise HomeAssistantError("Wrong tts file format!")

        key = KEY_PATTERN.format(
            record.group(1), record.group(2), record.group(3), record.group(4)
        )

        if key not in self.mem_cache:
            if key not in self.file_cache:
                raise HomeAssistantError(f"{key} not in cache!")
            await self.async_file_to_mem(key)

        content, _ = mimetypes.guess_type(filename)
        return content, self.mem_cache[key][MEM_CACHE_VOICE]

    @staticmethod
    def write_tags(filename, data, provider, message, language, options):
        """Write ID3 tags to file.

        Async friendly.
        """

        data_bytes = io.BytesIO(data)
        data_bytes.name = filename
        data_bytes.seek(0)

        album = provider.name
        artist = language

        if options is not None and options.get("voice") is not None:
            artist = options.get("voice")

        try:
            tts_file = mutagen.File(data_bytes, easy=True)
            if tts_file is not None:
                tts_file["artist"] = artist
                tts_file["album"] = album
                tts_file["title"] = message
                tts_file.save(data_bytes)
        except mutagen.MutagenError as err:
            _LOGGER.error("ID3 tag error: %s", err)

        return data_bytes.getvalue()


class Provider:
    """Represent a single TTS provider."""

    hass: Optional[HomeAssistantType] = None
    name: Optional[str] = None

    @property
    def default_language(self):
        """Return the default language."""
        return None

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return None

    @property
    def supported_options(self):
        """Return a list of supported options like voice, emotionen."""
        return None

    @property
    def default_options(self):
        """Return a dict include default options."""
        return None

    def get_tts_audio(self, message, language, options=None):
        """Load tts audio file from provider."""
        raise NotImplementedError()

    async def async_get_tts_audio(self, message, language, options=None):
        """Load tts audio file from provider.

        Return a tuple of file extension and data as bytes.
        """
        return await self.hass.async_add_executor_job(
            ft.partial(self.get_tts_audio, message, language, options=options)
        )


def _init_tts_cache_dir(hass, cache_dir):
    """Init cache folder."""
    if not os.path.isabs(cache_dir):
        cache_dir = hass.config.path(cache_dir)
    if not os.path.isdir(cache_dir):
        _LOGGER.info("Create cache dir %s", cache_dir)
        os.mkdir(cache_dir)
    return cache_dir


def _get_cache_files(cache_dir):
    """Return a dict of given engine files."""
    cache = {}

    folder_data = os.listdir(cache_dir)
    for file_data in folder_data:
        record = _RE_VOICE_FILE.match(file_data)
        if record:
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

    def __init__(self, tts):
        """Initialize a tts view."""
        self.tts = tts

    async def post(self, request):
        """Generate speech and provide url."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTP_BAD_REQUEST)
        if not data.get(ATTR_PLATFORM) and data.get(ATTR_MESSAGE):
            return self.json_message(
                "Must specify platform and message", HTTP_BAD_REQUEST
            )

        p_type = data[ATTR_PLATFORM]
        message = data[ATTR_MESSAGE]
        cache = data.get(ATTR_CACHE)
        language = data.get(ATTR_LANGUAGE)
        options = data.get(ATTR_OPTIONS)

        try:
            url = await self.tts.async_get_url(
                p_type, message, cache=cache, language=language, options=options
            )
            resp = self.json({"url": url}, HTTP_OK)
        except HomeAssistantError as err:
            _LOGGER.error("Error on init tts: %s", err)
            resp = self.json({"error": err}, HTTP_BAD_REQUEST)

        return resp


class TextToSpeechView(HomeAssistantView):
    """TTS view to serve a speech audio."""

    requires_auth = False
    url = "/api/tts_proxy/{filename}"
    name = "api:tts:speech"

    def __init__(self, tts):
        """Initialize a tts view."""
        self.tts = tts

    async def get(self, request, filename):
        """Start a get request."""
        try:
            content, data = await self.tts.async_read_tts(filename)
        except HomeAssistantError as err:
            _LOGGER.error("Error on load tts: %s", err)
            return web.Response(status=HTTP_NOT_FOUND)

        return web.Response(body=data, content_type=content)
