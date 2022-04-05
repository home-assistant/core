"""Support for the knovvu tts  service."""
import datetime
import json
import logging
import os

import requests

_LOGGER = logging.getLogger(__name__)

DOMAIN = "knovvu"

# Config
CONF_API_URL = "api_url"
CONF_API_TOKEN = "token"
CONF_URL_HASS = "base_url"
CONF_VOICE_NAME = "voice"
CONF_VOLUME = "volume"
CONF_RATE = "rate"

# Audio file path
CONF_FILE_PATH = "/config/www/tts/"
CON_AUDIO_PATH = "/local/tts/"

# Data service
ATTR_ENTITY_ID = "entity_id"
ATTR_MESSAGE = "message"


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def tts_handle(call):
        """Handle the service call."""
        # Config
        api_url = str(config[DOMAIN][CONF_API_URL])
        token = str(config[DOMAIN][CONF_API_TOKEN])
        base_url = str(config[DOMAIN][CONF_URL_HASS])
        voice = str(config[DOMAIN][CONF_VOICE_NAME])
        volume = str(config[DOMAIN][CONF_VOLUME])
        rate = str(config[DOMAIN][CONF_RATE])

        # Get data service
        entity_id = call.data[ATTR_ENTITY_ID]
        message = call.data[ATTR_MESSAGE]

        # HTTP Request
        url = api_url
        header = {"Authorization": token, "Content-Type": "application/json"}
        data_dict = {
            "Text": message,
            "Voice": {"Name": voice, "Volume": volume, "Rate": rate},
            "Audio": {
                "Format": "wav",
                "FormatDetails": {"Encoding": "pcm", "SampleRate": "24000"},
            },
        }

        response = requests.post(
            url, headers=header, verify=False, data=json.dumps(data_dict), stream=True
        )
        audio_bytes = response.raw.read()

        # Create unique audio file name
        uniq_filename = (
            "knovvu"
            + str(datetime.datetime.now().date())
            + "_"
            + str(datetime.datetime.now().time()).replace(":", ".")
            + ".wav"
        )

        wav_path = os.path.join(CONF_FILE_PATH, uniq_filename)
        with open(wav_path, mode="wb") as wav:
            wav.write(audio_bytes)

        # Play audio file with Home Assistant Service
        url_file = base_url + CON_AUDIO_PATH + uniq_filename

        # service data for 'CALL SERVICE' in Home Assistant
        service_data = {
            "entity_id": entity_id,
            "media_content_id": url_file,
            "media_content_type": "music",
        }

        # Call service from Home Assistant
        hass.services.call("media_player", "play_media", service_data)

    for file in os.listdir(CONF_FILE_PATH):
        os.remove(os.path.join(CONF_FILE_PATH, file))

    hass.services.register(DOMAIN, "knovvu_say", tts_handle)

    # Return boolean to indicate that initialization was successful.
    return True
