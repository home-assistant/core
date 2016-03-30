"""
Support for text to speech in Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/
"""

import logging
import re
import shutil
import hashlib
import os.path
import urllib.parse
import requests


from homeassistant import core
from homeassistant.const import (ATTR_ENTITY_ID, SERVICE_PLAY_MEDIA)
from homeassistant.components.media_player import (MEDIA_TYPE_MUSIC)

DEPENDENCIES = ['http']

DOMAIN = "tts"

SERVICE_SAY = "say"

ATTR_API_KEY = "key"
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
    """Register the process service."""
    config = config[DOMAIN]

    if config.get(ATTR_API_KEY) is None:
        _LOGGER.error("You must set a key in the tts configuration!")
        return False

    api_key = config.get(ATTR_API_KEY)

    tts_dir = hass.config.path(DOMAIN)

    if not os.path.exists(tts_dir):
        os.makedirs(tts_dir)

    hass.http.register_path(
        'GET', re.compile(r'/api/tts/(?P<tts_filename>.*)'),
        _handle_get_tts_file)

    # pylint: disable=too-many-locals
    def process(service):
        """Parse text into commands."""
        if ATTR_TEXT not in service.data:
            _LOGGER.error("Received process service call without text!")
            return

        text = service.data[ATTR_TEXT]
        entity_id = service.data.get(ATTR_ENTITY_ID)
        allow_cached_file = service.data.get(ATTR_ALLOW_CACHE, True)
        play_file = service.data.get(ATTR_PLAY, True)
        language = service.data.get(ATTR_LANGUAGE, config.get(ATTR_LANGUAGE,
                                                              "en-us"))
        rate = service.data.get(ATTR_RATE, config.get(ATTR_RATE, 0))
        codec = service.data.get(ATTR_CODEC, config.get(ATTR_CODEC, "MP3"))
        audio_format = service.data.get(ATTR_FORMAT,
                                        config.get(ATTR_FORMAT,
                                                   "44khz_16bit_stereo"))

        hashed_text = hashlib.sha1(text.encode('utf-8')).hexdigest()

        full_filename = "{}-{}-{}.{}".format(hashed_text, language,
                                             audio_format,
                                             codec.lower())

        file_path = os.path.join(tts_dir, full_filename)

        if os.path.isfile(file_path) is False or allow_cached_file is False:
            params = urllib.parse.urlencode({'key': api_key, 'src': text,
                                             'hl': language, 'r': rate,
                                             'c': codec, 'f': audio_format})
            url = "https://api.voicerss.org/?{}".format(params)
            tts_file = requests.get(url, stream=True)
            if tts_file.status_code == 200:
                with open(file_path, 'wb') as opened_file:
                    tts_file.raw.decode_content = True
                    shutil.copyfileobj(tts_file.raw, opened_file)
            else:
                err = "An error happened when requesting a file from VoiceRSS!"
                _LOGGER.error(err)

        if play_file is True or entity_id is None:
            hass_base_url = hass.config.api.base_url
            hass.services.call(core.DOMAIN, SERVICE_PLAY_MEDIA, {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MEDIA_CONTENT_ID: "{}/api/tts/{}".format(hass_base_url,
                                                              full_filename),
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC
            })

    hass.services.register(DOMAIN, SERVICE_SAY, process)

    return True


def _handle_get_tts_file(handler, path_match, data):
    """Return a TTS file."""
    handler.write_file(os.path.join(handler.server.hass.config.path(DOMAIN),
                                    path_match.group('tts_filename')))
