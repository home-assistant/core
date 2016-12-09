"""
Provide functionality to TTS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/
"""
import asyncio
import logging
import os

from aiohttp import web
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.bootstrap import (
    async_prepare_setup_platform, async_log_exception)
from homeassistant.core import callback
from homeassistant.config import load_yaml_config_file
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_MUSIC, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.util.yaml import dump

DOMAIN = 'tts'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

YAML_TTS_DB = 'tts_db.yaml'

CONF_LANG = 'language'
CONF_CACHE = 'cache'
CONF_CACHE_DIR = 'cache_dir'

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_LANG = 'en'

SERVICE_SAY_TEMPLATE = '{}_say'
SERVICE_SAY = 'say'

ATTR_MESSAGE = 'message'

DB_MESSAGE = 'message'
DB_FILE_NAME = 'file_name'
DB_PROVIDER = 'provider'


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): cv.string,
    vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
    vol.Optional(CONF_CACHE_DIR, default=DEFAULT_LANG): cv.string,
})


SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup TTS."""
    yaml_path = hass.config.path(YAML_TTS_DB)

    speech_db = yield from async_load_config(hass, yaml_path)
    store = SpeechStore(hass, speech_db)

    hass.http.register_view(TextToSpeechView(store))

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

            store.async_register_engine(p_type, provider, p_config)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        @asyncio.coroutine
        def async_say_handle(service):
            """Service handle for say."""
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            message = service.data.get(ATTR_MESSAGE)

            url = yield from store.async_get_url(p_type, message)
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
            DOMAIN, SERVICE_SAY_TEMPLATE.format(p_type), async_say_handle,
            descriptions.get(SERVICE_SAY))

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    return True


class SpeechStore(object):
    """Representation of a speech store."""

    def __init__(self, hass, speech_db):
        """Initialize a speech store."""
        self.hass = hass
        self.speech_db = speech_db
        self.providers = {}

        self._is_updating = asyncio.Lock(loop=hass.loop)

    @callback
    def async_register_engine(self, engine, provider, config):
        """Register a TTS provider."""
        provider.hass = self.hass
        provider.use_cache = config.get(CONF_CACHE)
        provider.language = config.get(CONF_LANG)

        cache_dir = yield from self.hass.loop.run_in_executor(
            None, tts_cache_dir, self.hass, config.get(CONF_CACHE_DIR))

        provider.cache_dir = cache_dir
        self.providers[engine] = provider

    @asyncio.coroutine
    def async_get_url(self, engine, message):
        """Get URL for play message.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        key = hash((engine, message))

        if provider.use_cache and key in self.speech_db:
            file_name = self.speech_db[key][DB_FILE_NAME]
        else:
            file_name = yield from self.async_save_tts(engine, key, message)
            if file_name is None:
                return None

        return "{}/{}/{}".format(
            self.hass.config.api.base_url, engine, file_name)

    @asyncio.coroutine
    def async_save_tts(self, engine, key, message):
        """Receive TTS and store for view.

        This method is a coroutine.
        """
        provider = self.providers[engine]
        data = yield from provider.async_run_tts(message)
        file_name = "{}_{}.{}".format(hash(message), engine,
                                      provider.file_format)

        if data is None:
            _LOGGER.error("No TTS from %s for '%s'", engine, message)
            return None

        def save_speech():
            """Store speech to filesystem."""
            with open(os.path.join(provider.cache_dir, file_name)) as speech:
                speech.write(data)

        try:
            yield from self.hass.loop.run_in_executor(None, save_speech)
        except OSError:
            _LOGGER.error("Can't write %s", file_name)
            return None

        if provider.use_cache:
            self.speech_db[key] = {
                DB_MESSAGE: message,
                DB_FILE_NAME: file_name,
                DB_PROVIDER: engine,
            }
            self.hass.async_add_job(
                self.async_update_db(key, self.speech_db[key]))

        return file_name

    @asyncio.coroutine
    def async_update_db(self, key, data):
        """Add device to YAML configuration file.

        This method is a coroutine.
        """
        with (yield from self._is_updating):
            yield from self.hass.loop.run_in_executor(
                None, update_db, self.hass.config.path(YAML_TTS_DB),
                key, data)


class Provider(object):
    """Represent a single provider."""

    hass = None
    use_cache = DEFAULT_CACHE
    cache_dir = DEFAULT_CACHE_DIR
    language = DEFAULT_LANG

    @property
    def file_format(self):
        """Return file/audio format."""
        raise NotImplementedError()

    @property
    def content_type(self):
        """Return file/audio format."""
        raise NotImplementedError()

    def run_tts(self, message):
        """Load tts audio file from provider."""
        raise NotImplementedError()

    @asyncio.coroutine
    def async_run_tts(self, message):
        """Load tts audio file from provider.

        This method is a coroutine.
        """
        data = yield from self.hass.loop.run_in_executor(
            None, self.run_tts, message)
        return data


class TextToSpeechView(HomeAssistantView):
    """TTS view to serve an speech audio."""

    requires_auth = False
    url = "/api/tts_proxy/{engine}/{audio_file}"
    name = "api:tts:speech"

    def __init__(self, store):
        """Initialize a tts view."""
        self.store = store

    @asyncio.coroutine
    def get(self, request, engine, audio_file):
        """Start a get request."""
        provider = self.store.providers.get(engine)
        if provider is None:
            _LOGGER.error("Engine not found: %s", engine)
            return web.Response(status=404)

        data = yield from request.app['hass'].loop.run_in_executor(
            None, load_speech,
            os.path.join(provider.cache_dir, audio_file)
        )
        if data is None:
            _LOGGER.error("Voice file not found: %s", audio_file)
            return web.Response(status=404)

        if not provider.use_cache:
            request.app['hass'].async_add_job(
                os.unlink,
                os.path.join(provider.cache_dir, audio_file)
            )

        return web.Response(body=data, content_type=provider.content_type)


@asyncio.coroutine
def async_load_config(hass, path):
    """Load TTS db from YAML configuration file.

    This method is a coroutine.
    """
    db_record_schema = vol.Schema({
        vol.Required(DB_MESSAGE): cv.string,
        vol.Required(DB_FILE_NAME): cv.string,
        vol.Required(DB_PROVIDER): cv.string,
    })

    try:
        result = {}
        try:
            db_data = yield from hass.loop.run_in_executor(
                None, load_yaml_config_file, path)
        except HomeAssistantError as err:
            _LOGGER.error('Unable to load %s: %s', path, str(err))
            return []

        for key, row in db_data.items():
            try:
                row = db_record_schema(row)
            except vol.Invalid as exp:
                async_log_exception(exp, key, row, hass)
            else:
                result[key] = row
        return result
    except (HomeAssistantError, FileNotFoundError):
        # When YAML file could not be loaded/did not contain a dict
        return {}


def tts_cache_dir(hass, cache_dir):
    """Init cache folder."""
    if not os.path.isabs(cache_dir):
        cache_dir = hass.config.path(cache_dir)

    if not os.path.isdir(cache_dir):
        _LOGGER.warning("Cache dir %s had not exists.", cache_dir)
        os.mkdir(cache_dir)

    return cache_dir


def update_db(path, key, data):
    """Add speech records to YAML configuration file."""
    with open(path, 'a') as out:
        record = {key: data}
        out.write('\n')
        out.write(dump(record))


def load_speech(path):
    """Load a speech from filesystem."""
    try:
        with open(path, 'r') as speech:
            return speech.read()
    except OSError:
        return None
