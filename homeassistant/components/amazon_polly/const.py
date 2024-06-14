"""Constants for the Amazon Polly text to speech service."""

from __future__ import annotations

from typing import Final

CONF_REGION: Final = "region_name"
CONF_ACCESS_KEY_ID: Final = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY: Final = "aws_secret_access_key"

CONF_ENGINE: Final = "engine"
CONF_VOICE: Final = "voice"
CONF_OUTPUT_FORMAT: Final = "output_format"
CONF_SAMPLE_RATE: Final = "sample_rate"
CONF_TEXT_TYPE: Final = "text_type"

SUPPORTED_OUTPUT_FORMATS: Final[set[str]] = {"mp3", "ogg_vorbis", "pcm"}

SUPPORTED_SAMPLE_RATES: Final[set[str]] = {"8000", "16000", "22050", "24000"}

SUPPORTED_SAMPLE_RATES_MAP: Final[dict[str, set[str]]] = {
    "mp3": {"8000", "16000", "22050", "24000"},
    "ogg_vorbis": {"8000", "16000", "22050"},
    "pcm": {"8000", "16000"},
}

SUPPORTED_TEXT_TYPES: Final[set[str]] = {"text", "ssml"}

CONTENT_TYPE_EXTENSIONS: Final[dict[str, str]] = {
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/pcm": "pcm",
}

DEFAULT_REGION: Final = "us-east-1"

DEFAULT_ENGINE: Final = "standard"
DEFAULT_VOICE: Final = "Joanna"
DEFAULT_OUTPUT_FORMAT: Final = "mp3"
DEFAULT_TEXT_TYPE: Final = "text"

DEFAULT_SAMPLE_RATES: Final[dict[str, str]] = {
    "mp3": "22050",
    "ogg_vorbis": "22050",
    "pcm": "16000",
}

AWS_CONF_CONNECT_TIMEOUT: Final = 10
AWS_CONF_READ_TIMEOUT: Final = 5
AWS_CONF_MAX_POOL_CONNECTIONS: Final = 1
