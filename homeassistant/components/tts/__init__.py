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
from homeassistant.helpers import config_per_platform
import homeassistant.helpers.config_validation as cv

DOMAIN = 'tts'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

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
    vol.Optional(CONF_CACHE_DIR, default=DEFAULT_LANG): cv.string,
})


SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CACHE): cv.boolean,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup TTS."""
    tts = SpeechStore(hass)

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

            url = yield from tts.async_get_url(p_type, message, cache=cache)
            if url is None:
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


class SpeechStore(object):
    """Representation of a speech store."""

    def __init__(self, hass):
        """Initialize a speech store."""
        self.hass = hass
        self.cache = {}
        self.providers = {}

    @callback
    def async_register_engine(self, engine, provider, config):
        """Register a TTS provider."""
        provider.hass = self.hass
        provider.use_cache = config.get(CONF_CACHE)
        provider.language = config.get(CONF_LANG)

        def tts_cache_dir(hass, cache_dir):
            """Init cache folder."""
            if not os.path.isabs(cache_dir):
                cache_dir = hass.config.path(cache_dir)
            if not os.path.isdir(cache_dir):
                _LOGGER.info("Create cache dir %s.", cache_dir)
                os.mkdir(cache_dir)
            return cache_dir

        cache_dir = yield from self.hass.loop.run_in_executor(
            None, tts_cache_dir, self.hass, config.get(CONF_CACHE_DIR))

        provider.cache_dir = cache_dir
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
            """Return a list of given engine files."""
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
            self.cache.update(cache_files)

    @asyncio.coroutine
    def async_get_url(self, engine, message, cache=None):
        """Get URL for play message.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        key = "{}_{}".format(hash(message), engine)
        use_cache = True if cache or provider.use_cache else False

        if use_cache and key in self.cache:
            file_name = self.cache[key]
        else:
            file_name = yield from self.async_save_tts(engine, key, message)
            if file_name is None:
                return None

        return "{}/{}".format(self.hass.config.api.base_url, file_name)

    @asyncio.coroutine
    def async_save_tts(self, engine, key, message):
        """Receive TTS and store for view.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        extension, data = yield from provider.async_get_tts_audio(message)
        file_name = "{}.{}".format(key, extension)

        if data is None:
            _LOGGER.error("No TTS from %s for '%s'", engine, message)
            return None

        def save_speech():
            """Store speech to filesystem."""
            voice_file = os.path.join(provider.cache_dir, file_name)
            with open(voice_file, 'wb') as speech:
                speech.write(data)

        try:
            yield from self.hass.loop.run_in_executor(None, save_speech)
        except OSError:
            _LOGGER.error("Can't write %s", file_name)
            return None

        if provider.use_cache:
            self.cache[key] = file_name

        return file_name

    def get_provider_from_filename(self, voice_file_name):
        """Return provider from voice file name.

        Async friendly.
        """
        record = _RE_VOICE_FILE.match(voice_file_name)
        if not record:
            return None

        return self.providers[record[1]]

    @asyncio.coroutine
    def async_read_tts(self, voice_file_name):
        """Read a voice file and return binary.

        This method is a coroutine.
        """
        provider = self.get_provider_from_filename(voice_file_name)
        if not provider:
            return None

        voice_file = os.path.join(provider.cache_dir, voice_file_name)

        def load_speech():
            """Load a speech from filesystem."""
            try:
                with open(voice_file, 'rb') as speech:
                    return speech.read()
            except OSError:
                return None

        data = yield from self.hass.loop.run_in_executor(None, load_speech)
        content, _ = mimetypes.guess_type(voice_file_name)

        if not provider.use_cache:
            self.hass.async_add_job(os.unlink, voice_file)

        return (content, data)


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
    url = "/api/tts_proxy/{voice_file_name}"
    name = "api:tts:speech"

    def __init__(self, tts):
        """Initialize a tts view."""
        self.tts = tts

    @asyncio.coroutine
    def get(self, request, voice_file_name):
        """Start a get request."""
        content, data = yield from self.tts.async_read_tts(voice_file_name)

        if data is None:
            _LOGGER.error("Voice file not found: %s", voice_file_name)
            return web.Response(status=404)

        return web.Response(body=data, content_type=content)
