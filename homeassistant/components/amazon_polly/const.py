"""Constants for the Amazon Polly text to speech service."""
from __future__ import annotations

from typing import Final

CONF_REGION: Final = "region_name"
CONF_ACCESS_KEY_ID: Final = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY: Final = "aws_secret_access_key"

DEFAULT_REGION: Final = "us-east-1"
SUPPORTED_REGIONS: Final[list[str]] = [
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

CONF_ENGINE: Final = "engine"
CONF_VOICE: Final = "voice"
CONF_OUTPUT_FORMAT: Final = "output_format"
CONF_SAMPLE_RATE: Final = "sample_rate"
CONF_TEXT_TYPE: Final = "text_type"

SUPPORTED_VOICES: Final[list[str]] = [
    "Aditi",  # Hindi
    "Amy",  # English (British)
    "Aria",  # English (New Zealand), Neural
    "Arlet",  # Catalan, Neural
    "Arthur",  # English, Neural
    "Astrid",  # Swedish
    "Ayanda",  # English (South African), Neural
    "Bianca",  # Italian
    "Brian",  # English (British)
    "Camila",  # Portuguese, Brazilian
    "Carla",  # Italian
    "Carmen",  # Romanian
    "Celine",  # French
    "Chantal",  # French Canadian
    "Conchita",  # Spanish (European)
    "Cristiano",  # Portuguese (European)
    "Daniel",  # German, Neural
    "Dora",  # Icelandic
    "Elin",  # Swedish, Neural
    "Emma",  # English
    "Enrique",  # Spanish (European)
    "Ewa",  # Polish
    "Filiz",  # Turkish
    "Gabrielle",  # French (Canadian)
    "Geraint",  # English Welsh
    "Giorgio",  # Italian
    "Gwyneth",  # Welsh
    "Hala",  # Arabic (Gulf), Neural
    "Hannah",  # German (Austrian), Neural
    "Hans",  # German
    "Hiujin",  # Chinese (Cantonese), Neural
    "Ida",  # Norwegian, Neural
    "Ines",  # Portuguese, European
    "Ivy",  # English
    "Jacek",  # Polish
    "Jan",  # Polish
    "Joanna",  # English
    "Joey",  # English
    "Justin",  # English
    "Kajal",  # English (Indian)/Hindi (Bilingual ), Neural
    "Karl",  # Icelandic
    "Kendra",  # English
    "Kevin",  # English, Neural
    "Kimberly",  # English
    "Laura",  # Dutch, Neural
    "Lea",  # French
    "Liam",  # Canadian French, Neural
    "Liv",  # Norwegian
    "Lotte",  # Dutch
    "Lucia",  # Spanish European
    "Lupe",  # Spanish US
    "Mads",  # Danish
    "Maja",  # Polish
    "Marlene",  # German
    "Mathieu",  # French
    "Matthew",  # English
    "Maxim",  # Russian
    "Mia",  # Spanish Mexican
    "Miguel",  # Spanish US
    "Mizuki",  # Japanese
    "Naja",  # Danish
    "Nicole",  # English Australian
    "Ola",  # Polish, Neural
    "Olivia",  # Female, Australian, Neural
    "Penelope",  # Spanish US
    "Pedro",  # Spanish US, Neural
    "Raveena",  # English, Indian
    "Ricardo",  # Portuguese (Brazilian)
    "Ruben",  # Dutch
    "Russell",  # English (Australian)
    "Ruth",  # English, Neural
    "Salli",  # English
    "Seoyeon",  # Korean
    "Stephen",  # English, Neural
    "Suvi",  # Finnish
    "Takumi",  # Japanese
    "Tatyana",  # Russian
    "Vicki",  # German
    "Vitoria",  # Portuguese, Brazilian
    "Zeina",  # Arabic
    "Zhiyu",  # Chinese
]

SUPPORTED_OUTPUT_FORMATS: Final[list[str]] = ["mp3", "ogg_vorbis", "pcm"]

SUPPORTED_ENGINES: Final[list[str]] = ["neural", "standard"]

SUPPORTED_SAMPLE_RATES: Final[list[str]] = ["8000", "16000", "22050", "24000"]

SUPPORTED_SAMPLE_RATES_MAP: Final[dict[str, list[str]]] = {
    "mp3": ["8000", "16000", "22050", "24000"],
    "ogg_vorbis": ["8000", "16000", "22050"],
    "pcm": ["8000", "16000"],
}

SUPPORTED_TEXT_TYPES: Final[list[str]] = ["text", "ssml"]

CONTENT_TYPE_EXTENSIONS: Final[dict[str, str]] = {
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/pcm": "pcm",
}

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
