"""
Provide functionality to TTS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/
"""
import asyncio
import logging
import mimetypes
import os
import re

from aiohttp import web
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.bootstrap import async_prepare_setup_platform
from homeassistant.core import callback
from homeassistant.config import load_yaml_config_file
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_MUSIC, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
import homeassistant.helpers.config_validation as cv

DOMAIN = 'tts'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

MEM_CACHE_TIME = 300
MEM_CACHE_FILENAME = 'filename'
MEM_CACHE_VOICE = 'voice'

CONF_LANG = 'language'
CONF_CACHE = 'cache'
CONF_CACHE_DIR = 'cache_dir'

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_LANG = 'en'

SERVICE_SAY = 'say'

ATTR_MESSAGE = 'message'
ATTR_CACHE = 'cache'

_RE_VOICE_FILE = re.compile(r"(\w)_(\w)\.\w{3,4}")

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): cv.string,
    vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
    vol.Optional(CONF_CACHE_DIR, default=DEFAULT_CACHE_DIR): cv.string,
})


SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CACHE): cv.boolean,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup TTS."""
    tts = SpeechManager(hass)

    hass.http.register_view(TextToSpeechView(tts))

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def async_setup_platform(p_type, p_config, disc_info=None):
        """Setup a tts platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            if hasattr(platform, 'async_get_engine'):
                provider = yield from platform.async_get_provider(
                    hass, p_config)
            else:
                provider = yield from hass.loop.run_in_executor(
                    None, platform.get_engine, hass, p_config)

            if provider is None:
                _LOGGER.error('Error setting up platform %s', p_type)
                return

            yield from tts.async_register_engine(p_type, provider, p_config)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        @asyncio.coroutine
        def async_say_handle(service):
            """Service handle for say."""
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            message = service.data.get(ATTR_MESSAGE)
            cache = service.data.get(ATTR_CACHE)

            try:
                url = yield from tts.async_get_url(
                    p_type, message, cache=cache)
            except HomeAssistantError as err:
                _LOGGER.error("Error on init tts: %s", err)
                return

            data = {
                ATTR_MEDIA_CONTENT_ID: url,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            }

            if entity_ids:
                data[ATTR_ENTITY_ID] = entity_ids

            yield from hass.services.async_call(
                DOMAIN_MP, SERVICE_PLAY_MEDIA, data, blocking=True)

        hass.services.async_register(
            DOMAIN, "{}_{}".format(p_type, SERVICE_SAY), async_say_handle,
            descriptions.get(SERVICE_SAY))

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    return True


class SpeechManager(object):
    """Representation of a speech store."""

    def __init__(self, hass):
        """Initialize a speech store."""
        self.hass = hass
        self.file_cache = {}
        self.mem_cache = {}
        self.providers = {}
        self._cache_dirs = {}

    @callback
    def async_register_engine(self, engine, provider, config):
        """Register a TTS provider."""
        provider.hass = self.hass
        provider.use_cache = config.get(CONF_CACHE)
        provider.language = config.get(CONF_LANG)
        cache_dir_key = config.get(CONF_CACHE_DIR)

        def tts_cache_dir(hass, cache_dir):
            """Init cache folder."""
            if not os.path.isabs(cache_dir):
                cache_dir = hass.config.path(cache_dir)
            if not os.path.isdir(cache_dir):
                _LOGGER.info("Create cache dir %s.", cache_dir)
                os.mkdir(cache_dir)
            return cache_dir

        if cache_dir_key in self._cache_dirs:
            provider.cache_dir = self._cache_dirs[cache_dir_key]
        else:
            provider.cache_dir = yield from self.hass.loop.run_in_executor(
                None, tts_cache_dir, self.hass, cache_dir_key)
            self._cache_dirs[cache_dir_key] = provider.cache_dir

        self.providers[engine] = provider
        if provider.use_cache:
            self.hass.async_add_job(self.async_load_engine_cache(engine))

    @asyncio.coroutine
    def async_load_engine_cache(self, engine):
        """Load cache from folder.

        This method is a coroutine.
        """
        provider = self.providers[engine]

        def get_cache_files():
            """Return a dict of given engine files."""
            cache = {}

            folder_data = os.listdir(provider.cache_dir)
            for file_data in folder_data:
                record = _RE_VOICE_FILE.match(file_data)
                if record and record[1] == engine:
                    key = "{}_{}".format(record[0], record[1])
                    cache[key] = file_data
            return cache

        cache_files = yield from self.hass.loop.run_in_executor(
            None, get_cache_files)

        if cache_files:
            self.file_cache.update(cache_files)

    @asyncio.coroutine
    def async_get_url(self, engine, message, cache=None):
        """Get URL for play message.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        key = "{}_{}".format(hash(message), engine)
        use_cache = cache if cache is not None else provider.use_cache

        # is speech allready in memory
        if key in self.mem_cache:
            filename = self.mem_cache[key][MEM_CACHE_FILENAME]
        # is file store in file cache
        elif use_cache and key in self.file_cache:
            filename = self.file_cache[key]
            self.hass.async_add_job(self.async_file_to_mem(engine, key))
        # load speech from provider into memory
        else:
            filename = yield from self.async_load_tts_audio(
                engine, key, message, use_cache)

        return "{}/{}".format(self.hass.config.api.base_url, filename)

    @asyncio.coroutine
    def async_load_tts_audio(self, engine, key, message, cache):
        """Receive TTS and store for view.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        extension, data = yield from provider.async_get_tts_audio(message)
        filename = "{}.{}".format(key, extension)
        voice_file = os.path.join(provider.cache_dir, filename)

        if data is None:
            raise HomeAssistantError("No TTS from %s for '%s'",
                                     engine, message)

        # save to memory
        self._async_store_to_memcache(key, filename, data)

        if cache:
            def save_speech():
                """Store speech to filesystem."""
                with open(voice_file, 'wb') as speech:
                    speech.write(data)

            try:
                yield from self.hass.loop.run_in_executor(None, save_speech)
                self.file_cache[key] = filename
            except OSError:
                raise HomeAssistantError("Can't write %s", filename)

        return filename

    @asyncio.coroutine
    def async_file_to_mem(self, engine, key):
        """Load voice from file cache into memory.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        filename = self.file_cache[key]

        voice_file = os.path.join(provider.cache_dir, filename)

        def load_speech():
            """Load a speech from filesystem."""
            with open(voice_file, 'rb') as speech:
                return speech.read()

        try:
            data = yield from self.hass.loop.run_in_executor(None, load_speech)
        except OSError:
            raise HomeAssistantError("Can't read %s", voice_file)

        self._async_store_to_memcache(key, filename, data)

    @callback
    def _async_store_to_memcache(self, key, filename, data):
        """Store data to memcache and set timer to remove it."""
        self.mem_cache[key] = {
            MEM_CACHE_FILENAME: filename,
            MEM_CACHE_VOICE: data,
        }

        @callback
        def async_remove_from_mem():
            """Cleanup memcache."""
            self.mem_cache.pop(key)

        self.hass.loop.call_later(MEM_CACHE_TIME, async_remove_from_mem)

    @asyncio.coroutine
    def async_read_tts(self, filename):
        """Read a voice file and return binary.

        This method is a coroutine.
        """
        record = _RE_VOICE_FILE.match(filename)
        if not record:
            raise HomeAssistantError("Wrong tts file format!")

        key = "{}_{}".format(record[0], record[1])
        engine = record[1]

        if key not in self.mem_cache:
            yield from self.async_file_to_mem(engine, key)

        content, _ = mimetypes.guess_type(filename)
        return (content, self.mem_cache[key][MEM_CACHE_VOICE])


class Provider(object):
    """Represent a single provider."""

    hass = None
    use_cache = DEFAULT_CACHE
    cache_dir = DEFAULT_CACHE_DIR
    language = DEFAULT_LANG

    def get_tts_audio(self, message):
        """Load tts audio file from provider."""
        raise NotImplementedError()

    @asyncio.coroutine
    def async_get_tts_audio(self, message):
        """Load tts audio file from provider.

        Return a tuple of file extension and data as bytes.

        This method is a coroutine.
        """
        extension, data = yield from self.hass.loop.run_in_executor(
            None, self.get_tts_audio, message)
        return (extension, data)


class TextToSpeechView(HomeAssistantView):
    """TTS view to serve an speech audio."""

    requires_auth = False
    url = "/api/tts_proxy/{filename}"
    name = "api:tts:speech"

    def __init__(self, tts):
        """Initialize a tts view."""
        self.tts = tts

    @asyncio.coroutine
    def get(self, request, filename):
        """Start a get request."""
        try:
            content, data = yield from self.tts.async_read_tts(filename)
        except HomeAssistantError as err:
            _LOGGER.error("Error on load tts: %s", err)
            return web.Response(status=404)

        return web.Response(body=data, content_type=content)
