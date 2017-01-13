"""
Support for the Amazon Polly text to speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/amazon_polly/
"""
import logging
import voluptuous as vol

from homeassistant.components.tts import Provider, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ["boto3==1.4.3"]

CONF_REGION = "region_name"
CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_PROFILE_NAME = "profile_name"
ATTR_CREDENTIALS = "credentials"

CONF_VOICE = "voice"
CONF_OUTPUT_FORMAT = "output_format"
CONF_SAMPLE_RATE = "sample_rate"
CONF_TEXT_TYPE = "text_type"

SUPPORTED_VOICES = ["Geraint", "Gwyneth", "Mads", "Naja", "Hans", "Marlene",
                    "Nicole", "Russell", "Amy", "Brian", "Emma", "Raveena",
                    "Ivy", "Joanna", "Joey", "Justin", "Kendra", "Kimberly",
                    "Salli", "Conchita", "Enrique", "Miguel", "Penelope",
                    "Chantal", "Celine", "Mathieu", "Dora", "Karl", "Carla",
                    "Giorgio", "Mizuki", "Liv", "Lotte", "Ruben", "Ewa",
                    "Jacek", "Jan", "Maja", "Ricardo", "Vitoria", "Cristiano",
                    "Ines", "Carmen", "Maxim", "Tatyana", "Astrid", "Filiz"]

SUPPORTED_OUTPUT_FORMATS = ["mp3", "ogg_vorbis", "pcm"]

SUPPORTED_SAMPLE_RATES = ["8000", "16000", "22050"]

SUPPORTED_SAMPLE_RATES_MAP = {
    "mp3": ["8000", "16000", "22050"],
    "ogg_vorbis": ["8000", "16000", "22050"],
    "pcm": ["8000", "16000"]
}

SUPPORTED_TEXT_TYPES = ["text", "ssml"]

CONTENT_TYPE_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/pcm": "pcm"
}

DEFAULT_VOICE = "Joanna"
DEFAULT_OUTPUT_FORMAT = "mp3"
DEFAULT_TEXT_TYPE = "text"

DEFAULT_SAMPLE_RATES = {
    "mp3": "22050",
    "ogg_vorbis": "22050",
    "pcm": "16000"
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_REGION, default="us-east-1"): cv.string,
    vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
    vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
    vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
    vol.Optional(CONF_VOICE, default=DEFAULT_VOICE):
        vol.In(SUPPORTED_VOICES),
    vol.Optional(CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT):
        vol.In(SUPPORTED_OUTPUT_FORMATS),
    vol.Optional(CONF_SAMPLE_RATE): vol.All(cv.string,
                                            vol.In(SUPPORTED_SAMPLE_RATES)),
    vol.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE):
        vol.In(SUPPORTED_TEXT_TYPES),
})


def get_engine(hass, config):
    """Setup Amazon Polly speech component."""
    # pylint: disable=import-error
    output_format = config.get(CONF_OUTPUT_FORMAT)
    sample_rate = config.get(CONF_SAMPLE_RATE,
                             DEFAULT_SAMPLE_RATES[output_format])
    if sample_rate not in SUPPORTED_SAMPLE_RATES_MAP.get(output_format):
        _LOGGER.error("%s is not a valid sample rate for %s",
                      sample_rate, output_format)
        return None

    import boto3

    profile = config.get(CONF_PROFILE_NAME)

    if profile is not None:
        boto3.setup_default_session(profile_name=profile)

    aws_config = {
        CONF_REGION: config.get(CONF_REGION),
        CONF_ACCESS_KEY_ID: config.get(CONF_ACCESS_KEY_ID),
        CONF_SECRET_ACCESS_KEY: config.get(CONF_SECRET_ACCESS_KEY),
    }

    polly_client = boto3.client("polly", **aws_config)

    def find_voice_language():
        """Get the language code for the chosen voice."""
        all_voices = polly_client.describe_voices()
        for voice in all_voices.get("Voices"):
            if voice.get("Id", "") == config.get(CONF_VOICE):
                return "{}-{}".format(config.get(CONF_VOICE).lower(),
                                      voice.get("LanguageCode"))

    voice_language = find_voice_language()

    return AmazonPollyProvider(polly_client, config, voice_language)


class AmazonPollyProvider(Provider):
    """Amazon Polly speech api provider."""

    def __init__(self, polly_client, config, voice_language):
        """Initialize Amazon Polly provider for TTS."""
        self.client = polly_client
        self.config = config
        self.language = voice_language

    def get_tts_audio(self, message, language=None):
        """Request TTS file from Polly."""
        resp = self.client.synthesize_speech(
            OutputFormat=self.config[CONF_OUTPUT_FORMAT],
            SampleRate=self.config[CONF_SAMPLE_RATE],
            Text=message,
            TextType=self.config[CONF_TEXT_TYPE],
            VoiceId=self.config[CONF_VOICE]
        )

        return (CONTENT_TYPE_EXTENSIONS[resp.get("ContentType")],
                resp.get("AudioStream").read())
