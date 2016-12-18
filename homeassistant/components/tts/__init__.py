"""
Provide functionality to TTS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/
"""
import asyncio
import logging
import hashlib
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

MEM_CACHE_FILENAME = 'filename'
MEM_CACHE_VOICE = 'voice'

CONF_LANG = 'language'
CONF_CACHE = 'cache'
CONF_CACHE_DIR = 'cache_dir'
CONF_TIME_MEMORY = 'time_memory'

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300

SERVICE_SAY = 'say'
SERVICE_CLEAR_CACHE = 'clear_cache'

ATTR_MESSAGE = 'message'
ATTR_CACHE = 'cache'

_RE_VOICE_FILE = re.compile(r"([a-f0-9]{40})_([a-z]+)\.[a-z0-9]{3,4}")

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
    vol.Optional(CONF_CACHE_DIR, default=DEFAULT_CACHE_DIR): cv.string,
    vol.Optional(CONF_TIME_MEMORY, default=DEFAULT_TIME_MEMORY):
        vol.All(vol.Coerce(int), vol.Range(min=60, max=57600)),
})


SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CACHE): cv.boolean,
})

SCHEMA_SERVICE_CLEAR_CACHE = vol.Schema({})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup TTS."""
    tts = SpeechManager(hass)

    try:
        conf = config[DOMAIN][0] if len(config.get(DOMAIN, [])) > 0 else {}
        use_cache = conf.get(CONF_CACHE, DEFAULT_CACHE)
        cache_dir = conf.get(CONF_CACHE_DIR, DEFAULT_CACHE_DIR)
        time_memory = conf.get(CONF_TIME_MEMORY, DEFAULT_TIME_MEMORY)

        yield from tts.async_init_cache(use_cache, cache_dir, time_memory)
    except (HomeAssistantError, KeyError) as err:
        _LOGGER.error("Error on cache init %s", err)
        return False

    hass.http.register_view(TextToSpeechView(tts))

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config, disc_info=None):
        """Setup a tts platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            if hasattr(platform, 'async_get_engine'):
                provider = yield from platform.async_get_engine(
                    hass, p_config)
            else:
                provider = yield from hass.loop.run_in_executor(
                    None, platform.get_engine, hass, p_config)

            if provider is None:
                _LOGGER.error('Error setting up platform %s', p_type)
                return

            tts.async_register_engine(p_type, provider, p_config)
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
            descriptions.get(SERVICE_SAY), schema=SCHEMA_SERVICE_SAY)

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_clear_cache_handle(service):
        """Handle clear cache service call."""
        yield from tts.async_clear_cache()

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_CACHE, async_clear_cache_handle,
        descriptions.get(SERVICE_CLEAR_CACHE),
        schema=SCHEMA_SERVICE_CLEAR_CACHE)

    return True


class SpeechManager(object):
    """Representation of a speech store."""

    def __init__(self, hass):
        """Initialize a speech store."""
        self.hass = hass
        self.providers = {}

        self.use_cache = DEFAULT_CACHE
        self.cache_dir = DEFAULT_CACHE_DIR
        self.time_memory = DEFAULT_TIME_MEMORY
        self.file_cache = {}
        self.mem_cache = {}

    @asyncio.coroutine
    def async_init_cache(self, use_cache, cache_dir, time_memory):
        """Init config folder and load file cache."""
        self.use_cache = use_cache
        self.time_memory = time_memory

        def init_tts_cache_dir(cache_dir):
            """Init cache folder."""
            if not os.path.isabs(cache_dir):
                cache_dir = self.hass.config.path(cache_dir)
            if not os.path.isdir(cache_dir):
                _LOGGER.info("Create cache dir %s.", cache_dir)
                os.mkdir(cache_dir)
            return cache_dir

        try:
            self.cache_dir = yield from self.hass.loop.run_in_executor(
                None, init_tts_cache_dir, cache_dir)
        except OSError as err:
            raise HomeAssistantError(
                "Can't init cache dir {}".format(err))

        def get_cache_files():
            """Return a dict of given engine files."""
            cache = {}

            folder_data = os.listdir(self.cache_dir)
            for file_data in folder_data:
                record = _RE_VOICE_FILE.match(file_data)
                if record:
                    key = "{}_{}".format(record.group(1), record.group(2))
                    cache[key.lower()] = file_data.lower()
            return cache

        try:
            cache_files = yield from self.hass.loop.run_in_executor(
                None, get_cache_files)
        except OSError as err:
            raise HomeAssistantError(
                "Can't read cache dir {}".format(err))

        if cache_files:
            self.file_cache.update(cache_files)

    @asyncio.coroutine
    def async_clear_cache(self):
        """Read file cache and delete files."""
        self.mem_cache = {}

        def remove_files():
            """Remove files from filesystem."""
            for _, filename in self.file_cache.items():
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError:
                    pass

        yield from self.hass.loop.run_in_executor(None, remove_files)
        self.file_cache = {}

    @callback
    def async_register_engine(self, engine, provider, config):
        """Register a TTS provider."""
        provider.hass = self.hass
        provider.language = config.get(CONF_LANG)
        self.providers[engine] = provider

    @asyncio.coroutine
    def async_get_url(self, engine, message, cache=None):
        """Get URL for play message.

        This method is a coroutine.
        """
        msg_hash = hashlib.sha1(bytes(message, 'utf-8')).hexdigest()
        key = ("{}_{}".format(msg_hash, engine)).lower()
        use_cache = cache if cache is not None else self.use_cache

        # is speech allready in memory
        if key in self.mem_cache:
            filename = self.mem_cache[key][MEM_CACHE_FILENAME]
        # is file store in file cache
        elif use_cache and key in self.file_cache:
            filename = self.file_cache[key]
            self.hass.async_add_job(self.async_file_to_mem(engine, key))
        # load speech from provider into memory
        else:
            filename = yield from self.async_get_tts_audio(
                engine, key, message, use_cache)

        return "{}/api/tts_proxy/{}".format(
            self.hass.config.api.base_url, filename)

    @asyncio.coroutine
    def async_get_tts_audio(self, engine, key, message, cache):
        """Receive TTS and store for view in cache.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        extension, data = yield from provider.async_get_tts_audio(message)

        if data is None or extension is None:
            raise HomeAssistantError(
                "No TTS from {} for '{}'".format(engine, message))

        # create file infos
        filename = ("{}.{}".format(key, extension)).lower()

        # save to memory
        self._async_store_to_memcache(key, filename, data)

        if cache:
            self.hass.async_add_job(
                self.async_save_tts_audio(key, filename, data))

        return filename

    @asyncio.coroutine
    def async_save_tts_audio(self, key, filename, data):
        """Store voice data to file and file_cache.

        This method is a coroutine.
        """
        voice_file = os.path.join(self.cache_dir, filename)

        def save_speech():
            """Store speech to filesystem."""
            with open(voice_file, 'wb') as speech:
                speech.write(data)

        try:
            yield from self.hass.loop.run_in_executor(None, save_speech)
            self.file_cache[key] = filename
        except OSError:
            _LOGGER.error("Can't write %s", filename)

    @asyncio.coroutine
    def async_file_to_mem(self, engine, key):
        """Load voice from file cache into memory.

        This method is a coroutine.
        """
        filename = self.file_cache.get(key)
        if not filename:
            raise HomeAssistantError("Key {} not in file cache!".format(key))

        voice_file = os.path.join(self.cache_dir, filename)

        def load_speech():
            """Load a speech from filesystem."""
            with open(voice_file, 'rb') as speech:
                return speech.read()

        try:
            data = yield from self.hass.loop.run_in_executor(None, load_speech)
        except OSError:
            raise HomeAssistantError("Can't read {}".format(voice_file))

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

        self.hass.loop.call_later(self.time_memory, async_remove_from_mem)

    @asyncio.coroutine
    def async_read_tts(self, filename):
        """Read a voice file and return binary.

        This method is a coroutine.
        """
        record = _RE_VOICE_FILE.match(filename.lower())
        if not record:
            raise HomeAssistantError("Wrong tts file format!")

        key = "{}_{}".format(record.group(1), record.group(2))

        if key not in self.mem_cache:
            if key not in self.file_cache:
                raise HomeAssistantError("%s not in cache!", key)
            engine = record.group(2)
            yield from self.async_file_to_mem(engine, key)

        content, _ = mimetypes.guess_type(filename)
        return (content, self.mem_cache[key][MEM_CACHE_VOICE])


class Provider(object):
    """Represent a single provider."""

    hass = None
    language = None

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
