"""Support for the Amazon Polly text to speech service."""
import logging

import boto3
import voluptuous as vol

from homeassistant.components.tts import PLATFORM_SCHEMA, Provider
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_REGION = "region_name"
CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_PROFILE_NAME = "profile_name"
ATTR_CREDENTIALS = "credentials"

DEFAULT_REGION = "us-east-1"
SUPPORTED_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "ca-central-1",
    "eu-west-1",
    "eu-central-1",
    "eu-west-2",
    "eu-west-3",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-2",
    "ap-northeast-1",
    "ap-south-1",
    "sa-east-1",
]

CONF_ENGINE = "engine"
CONF_VOICE = "voice"
CONF_OUTPUT_FORMAT = "output_format"
CONF_SAMPLE_RATE = "sample_rate"
CONF_TEXT_TYPE = "text_type"

SUPPORTED_VOICES = [
    "Zhiyu",  # Chinese
    "Mads",
    "Naja",  # Danish
    "Ruben",
    "Lotte",  # Dutch
    "Russell",
    "Nicole",  # English Australian
    "Brian",
    "Amy",
    "Emma",  # English
    "Aditi",
    "Raveena",  # English, Indian
    "Joey",
    "Justin",
    "Matthew",
    "Ivy",
    "Joanna",
    "Kendra",
    "Kimberly",
    "Salli",  # English
    "Geraint",  # English Welsh
    "Mathieu",
    "Celine",
    "Lea",  # French
    "Chantal",  # French Canadian
    "Hans",
    "Marlene",
    "Vicki",  # German
    "Aditi",  # Hindi
    "Karl",
    "Dora",  # Icelandic
    "Giorgio",
    "Carla",
    "Bianca",  # Italian
    "Takumi",
    "Mizuki",  # Japanese
    "Seoyeon",  # Korean
    "Liv",  # Norwegian
    "Jacek",
    "Jan",
    "Ewa",
    "Maja",  # Polish
    "Ricardo",
    "Vitoria",  # Portuguese, Brazilian
    "Cristiano",
    "Ines",  # Portuguese, European
    "Carmen",  # Romanian
    "Maxim",
    "Tatyana",  # Russian
    "Enrique",
    "Conchita",
    "Lucia",  # Spanish European
    "Mia",  # Spanish Mexican
    "Miguel",  # Spanish US
    "Penelope",  # Spanish US
    "Lupe",  # Spanish US
    "Astrid",  # Swedish
    "Filiz",  # Turkish
    "Gwyneth",  # Welsh
]

SUPPORTED_OUTPUT_FORMATS = ["mp3", "ogg_vorbis", "pcm"]

SUPPORTED_ENGINES = ["neural", "standard"]

SUPPORTED_SAMPLE_RATES = ["8000", "16000", "22050", "24000"]

SUPPORTED_SAMPLE_RATES_MAP = {
    "mp3": ["8000", "16000", "22050", "24000"],
    "ogg_vorbis": ["8000", "16000", "22050"],
    "pcm": ["8000", "16000"],
}

SUPPORTED_TEXT_TYPES = ["text", "ssml"]

CONTENT_TYPE_EXTENSIONS = {"audio/mpeg": "mp3", "audio/ogg": "ogg", "audio/pcm": "pcm"}

DEFAULT_ENGINE = "standard"
DEFAULT_VOICE = "Joanna"
DEFAULT_OUTPUT_FORMAT = "mp3"
DEFAULT_TEXT_TYPE = "text"

DEFAULT_SAMPLE_RATES = {"mp3": "22050", "ogg_vorbis": "22050", "pcm": "16000"}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
        vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
        vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORTED_VOICES),
        vol.Optional(CONF_ENGINE, default=DEFAULT_ENGINE): vol.In(SUPPORTED_ENGINES),
        vol.Optional(CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT): vol.In(
            SUPPORTED_OUTPUT_FORMATS
        ),
        vol.Optional(CONF_SAMPLE_RATE): vol.All(
            cv.string, vol.In(SUPPORTED_SAMPLE_RATES)
        ),
        vol.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): vol.In(
            SUPPORTED_TEXT_TYPES
        ),
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up Amazon Polly speech component."""
    output_format = config[CONF_OUTPUT_FORMAT]
    sample_rate = config.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATES[output_format])
    if sample_rate not in SUPPORTED_SAMPLE_RATES_MAP.get(output_format):
        _LOGGER.error(
            "%s is not a valid sample rate for %s", sample_rate, output_format
        )
        return None

    config[CONF_SAMPLE_RATE] = sample_rate

    profile = config.get(CONF_PROFILE_NAME)

    if profile is not None:
        boto3.setup_default_session(profile_name=profile)

    aws_config = {
        CONF_REGION: config[CONF_REGION],
        CONF_ACCESS_KEY_ID: config.get(CONF_ACCESS_KEY_ID),
        CONF_SECRET_ACCESS_KEY: config.get(CONF_SECRET_ACCESS_KEY),
    }

    del config[CONF_REGION]
    del config[CONF_ACCESS_KEY_ID]
    del config[CONF_SECRET_ACCESS_KEY]

    polly_client = boto3.client("polly", **aws_config)

    supported_languages = []

    all_voices = {}

    all_voices_req = polly_client.describe_voices()

    for voice in all_voices_req.get("Voices"):
        all_voices[voice.get("Id")] = voice
        if voice.get("LanguageCode") not in supported_languages:
            supported_languages.append(voice.get("LanguageCode"))

    return AmazonPollyProvider(polly_client, config, supported_languages, all_voices)


class AmazonPollyProvider(Provider):
    """Amazon Polly speech api provider."""

    def __init__(self, polly_client, config, supported_languages, all_voices):
        """Initialize Amazon Polly provider for TTS."""
        self.client = polly_client
        self.config = config
        self.supported_langs = supported_languages
        self.all_voices = all_voices
        self.default_voice = self.config[CONF_VOICE]
        self.name = "Amazon Polly"

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return self.supported_langs

    @property
    def default_language(self):
        """Return the default language."""
        return self.all_voices.get(self.default_voice).get("LanguageCode")

    @property
    def default_options(self):
        """Return dict include default options."""
        return {CONF_VOICE: self.default_voice}

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return [CONF_VOICE]

    def get_tts_audio(self, message, language=None, options=None):
        """Request TTS file from Polly."""
        voice_id = options.get(CONF_VOICE, self.default_voice)
        voice_in_dict = self.all_voices.get(voice_id)
        if language != voice_in_dict.get("LanguageCode"):
            _LOGGER.error("%s does not support the %s language", voice_id, language)
            return None, None

        resp = self.client.synthesize_speech(
            Engine=self.config[CONF_ENGINE],
            OutputFormat=self.config[CONF_OUTPUT_FORMAT],
            SampleRate=self.config[CONF_SAMPLE_RATE],
            Text=message,
            TextType=self.config[CONF_TEXT_TYPE],
            VoiceId=voice_id,
        )

        return (
            CONTENT_TYPE_EXTENSIONS[resp.get("ContentType")],
            resp.get("AudioStream").read(),
        )
