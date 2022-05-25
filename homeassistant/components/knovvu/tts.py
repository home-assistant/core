"""Support for the Knovvu speech service."""
import json
import logging
import os

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import jwt
import requests
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORT_CODECS = ["mp3", "wav", "opus"]

SUPPORT_SAMPLE_RATE = [16000, 24000]

SUPPORT_VOICES = [
    "Sestek Rae 24k",
    "Sestek Sinan 24k",
    "Sestek Delal 24k",
    "Sestek Melissa 24k",
    "Sestek Gul 24k_HV_Premium",
    "Sestek Annabella 24k",
    "Sestek Darya 24k",
    "Sestek Deepti 24k",
    "Sestek Elif 24k",
    "Sestek Gladys 24k",
    "Sestek Guldestan 24k",
    "Sestek Johannes 24k",
    "Sestek Kristina 24k",
    "Sestek Marie 24k",
    "Sestek Muntaha 24k",
    "Sestek Murad 24k",
    "Sestek Oliver 24k",
    "Sestek Silas 24k",
    "Sestek Ulviye 24k",
    "Sestek Yasmin 24k",
    "Sestek Yousef 24k",
]

SUPPORT_LANGUAGES = SUPPORT_VOICES

MIN_RATE = 0.3
MAX_RATE = 3

MIN_VOLUME = 0.0
MAX_VOLUME = 2

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_URL_TOKEN = "url_token"
CONF_CODEC = "codec"
CONF_VOICE = "voice"
CONF_VOLUME = "volume"
CONF_RATE = "rate"
CONF_SAMPLE_RATE = "sample_rate"

DEFAULT_URL = "https://ttsapi.knovvu.com/v1/speech/synthesis/tts"
DEFAULT_URL_TOKEN = "https://identity.ldm.knovvu.com/connect/token"
DEFAULT_CODEC = "wav"
DEFAULT_LANG = "Sestek Gul 24k_HV_Premium"
DEFAULT_VOICE = "Sestek Gul 24k_HV_Premium"
DEFAULT_VOLUME = 1
DEFAULT_RATE = 1
DEFAULT_SAMPLE_RATE = 24000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_URL_TOKEN, default=DEFAULT_URL_TOKEN): cv.string,
        vol.Optional(CONF_URL, default=DEFAULT_URL): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_CODEC, default=DEFAULT_CODEC): vol.In(SUPPORT_CODECS),
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORT_VOICES),
        vol.Optional(CONF_SAMPLE_RATE, default=DEFAULT_SAMPLE_RATE): vol.In(
            SUPPORT_SAMPLE_RATE
        ),
        vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.Range(
            min=MIN_RATE, max=MAX_RATE
        ),
        vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): vol.Range(
            min=MIN_VOLUME, max=MAX_VOLUME
        ),
    }
)

SUPPORTED_OPTIONS = [CONF_CODEC, CONF_VOICE, CONF_RATE, CONF_VOLUME, CONF_SAMPLE_RATE]


async def async_get_engine(hass, config, discovery_info=None):
    """Set up knovvu speech component."""
    return KnovvuProvider(hass, config)


class KnovvuProvider(Provider):
    """The knovvu speech API provider."""

    def __init__(self, hass, conf):
        """Init knovvu TTS service."""
        self.hass = hass
        self._key = conf.get(CONF_URL)
        self._url_token = conf.get(CONF_URL_TOKEN)
        self._id = conf.get(CONF_CLIENT_ID)
        self._secret = conf.get(CONF_CLIENT_SECRET)
        self._codec = conf.get(CONF_CODEC)
        self._language = conf.get(CONF_LANG)
        self._voice = conf.get(CONF_VOICE)
        self._volume = conf.get(CONF_VOLUME)
        self._rate = conf.get(CONF_RATE)
        self._sample_rate = conf.get(CONF_SAMPLE_RATE)
        self.name = "Knovvu"

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self):
        """Return list of supported options."""
        return SUPPORTED_OPTIONS

    def get_tts_audio(self, message, language, options=None):
        """Request TTS file from Knovvu."""
        options = options or {}
        output_format = options.get(CONF_CODEC, self._codec)

        if os.path.exists("encryptedldmtoken.bin"):

            # Decryption
            with open("encryptedldmtoken.bin", "rb") as file_in:
                nonce, tag, ciphertext = (file_in.read(x) for x in (16, 16, -1))
            file_in.close()

            with open("key.bin", "rb") as ffile:
                key = ffile.readline()
            ffile.close()

            cipher = AES.new(key, AES.MODE_EAX, nonce)
            token = cipher.decrypt_and_verify(ciphertext, tag)
            token = token.decode("utf-8")

            token_data = token.split()
            decoded = jwt.decode(token_data[1], options={"verify_signature": False})
            expiry_date = decoded["exp"]

            if expiry_date < 5000:
                os.remove("ldmtoken.txt")
                _LOGGER.warning(
                    "Expiration date is less than 5000. Token is refreshing. : %s",
                    expiry_date,
                )
        else:
            url_token = self._url_token
            header = {
                "client_id": self._id,
                "client_secret": self._secret,
                "grant_type": "client_credentials",
                "scop": "Ldm_Integration",
                "Content-Type": "application/json",
            }
            ldm_token = requests.post(url=url_token, data=header, verify=False)

            data = ldm_token.json()
            token = data["token_type"] + " " + data["access_token"]

            # Encryption
            key = get_random_bytes(16)
            cipher = AES.new(key, AES.MODE_EAX)
            ciphertext, tag = cipher.encrypt_and_digest(token.encode("utf-8"))

            with open("encryptedldmtoken.bin", "wb") as file_out:
                for chiper_iter in (cipher.nonce, tag, ciphertext):
                    file_out.write(chiper_iter)
            file_out.close()

            with open("key.bin", "wb") as ffile:
                ffile.write(key)
            ffile.close()

        url = self._key
        header = {"Authorization": token, "Content-Type": "application/json"}
        data_dict = {
            "Text": message,
            "Voice": {
                "Name": options.get(CONF_VOICE, self._voice),
                "Volume": options.get(CONF_VOLUME, self._volume),
                "Rate": options.get(CONF_RATE, self._rate),
            },
            "Audio": {
                "Format": output_format,
                "FormatDetails": {
                    "Encoding": "pcm",
                    "SampleRate": options.get(CONF_SAMPLE_RATE, self._sample_rate),
                },
            },
        }

        response = requests.post(
            url, headers=header, verify=False, data=json.dumps(data_dict), stream=True
        )
        audio_bytes = response.raw.read()

        return (output_format, audio_bytes)
