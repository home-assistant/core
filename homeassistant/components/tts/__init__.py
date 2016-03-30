"""
Support for text to speech in Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/
"""

import logging
import re
import hashlib
import os.path
from functools import partial

from homeassistant import core
import homeassistant.bootstrap as bootstrap
from homeassistant.helpers import config_per_platform
from homeassistant.const import (ATTR_ENTITY_ID, SERVICE_PLAY_MEDIA, CONF_NAME)
from homeassistant.components.media_player import MEDIA_TYPE_MUSIC
from homeassistant.config import load_yaml_config_file

DEPENDENCIES = ['http']

DOMAIN = "tts"

SERVICE_TTS = "tts"

ATTR_TEXT = "text"
ATTR_ALLOW_CACHE = "allow_cached_file"
ATTR_PLAY = "play"
ATTR_LANGUAGE = "language"
ATTR_RATE = "rate"
ATTR_CODEC = "codec"
ATTR_FORMAT = "format"
ATTR_MEDIA_CONTENT_ID = "media_content_id"
ATTR_MEDIA_CONTENT_TYPE = "media_content_type"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the tts service."""
    success = False

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    tts_dir = hass.config.path(DOMAIN)

    if not os.path.exists(tts_dir):
        os.makedirs(tts_dir)

    for platform, p_config in config_per_platform(config, DOMAIN, _LOGGER):
        tts_implementation = bootstrap.prepare_setup_platform(
            hass, config, DOMAIN, platform)

        if tts_implementation is None:
            _LOGGER.error("Unknown tts service specified.")
            continue

        tts_engine = tts_implementation.get_engine(hass, p_config)

        if tts_engine is None:
            _LOGGER.error("Failed to initialize tts service %s",
                          platform)
            continue

        def generate_speech(tts_service, platform_name, call):
            """Handle sending tts message service calls."""
            text = call.data.get(ATTR_TEXT)
            entity_id = call.data.get(ATTR_ENTITY_ID)
            allow_cached_file = call.data.get(ATTR_ALLOW_CACHE, True)
            play_file = call.data.get(ATTR_PLAY, True)
            language = call.data.get(ATTR_LANGUAGE, config.get(ATTR_LANGUAGE,
                                                               "en-us"))
            rate = call.data.get(ATTR_RATE, config.get(ATTR_RATE, 0))
            codec = call.data.get(ATTR_CODEC, config.get(ATTR_CODEC, "MP3"))
            audio_format = call.data.get(ATTR_FORMAT,
                                         config.get(ATTR_FORMAT,
                                                    "44khz_16bit_stereo"))

            hashed_text = hashlib.sha1(text.encode('utf-8')).hexdigest()

            full_filename = "{}-{}-{}.{}".format(hashed_text, language,
                                                 platform_name,
                                                 codec.lower())

            file_path = os.path.join(tts_dir, full_filename)

            if text is None:
                _LOGGER.error(
                    'Received call to %s without attribute %s',
                    call.service, ATTR_TEXT)
                return

            if (os.path.isfile(file_path)) is False or \
               (allow_cached_file is False):
                try:
                    tts_service.speak(file_path, text, language, rate, codec,
                                      audio_format)
                # pylint: disable=bare-except
                except:
                    _LOGGER.error('Error trying to speak using %s',
                                  platform_name)
                    return

            if play_file is True or entity_id is None:
                content_url = "{}/api/tts/{}".format(hass.config.api.base_url,
                                                     full_filename)
                hass.services.call(core.DOMAIN, SERVICE_PLAY_MEDIA, {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_MEDIA_CONTENT_ID: content_url,
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC
                })

        service_tts = p_config.get(CONF_NAME, platform)
        service_call_handler = partial(generate_speech, tts_engine,
                                       service_tts)
        hass.services.register(DOMAIN, service_tts, service_call_handler,
                               descriptions.get(SERVICE_TTS))
        success = True

    hass.http.register_path(
        'GET', re.compile(r'/api/tts/(?P<tts_filename>.*)'),
        _handle_get_tts_file)

    return success


def _handle_get_tts_file(handler, path_match, data):
    """Return a TTS file."""
    handler.write_file(os.path.join(handler.server.hass.config.path(DOMAIN),
                                    path_match.group('tts_filename')))

# pylint: disable=too-few-public-methods


class BaseTTSService(object):
    """An abstract class for TTS services."""

    # pylint: disable=too-many-arguments
    def speak(self, file_path, text, language, rate, codec, audio_format):
        """Speak something."""
        raise NotImplementedError
