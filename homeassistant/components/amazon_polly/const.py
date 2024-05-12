"""Constants for the Amazon Polly text to speech service."""

from __future__ import annotations

from typing import Final

CONF_REGION: Final = "region_name"
CONF_ACCESS_KEY_ID: Final = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY: Final = "aws_secret_access_key"

DEFAULT_REGION: Final = "us-east-1"
SUPPORTED_REGIONS: Final[list[str]] = [
    "af-south-1",
    "ap-east-1",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-south-1",
    "ap-south-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-southeast-3",
    "ap-southeast-4",
    "ca-central-1",
    "ca-west-1",
    "eu-central-1",
    "eu-central-2",
    "eu-north-1",
    "eu-south-1",
    "eu-south-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "il-central-1",
    "me-central-1",
    "me-south-1",
    "sa-east-1",
    "us-east-1",
    "us-east-2",
    "us-gov-east-1",
    "us-gov-west-1",
    "us-west-1",
    "us-west-2",
]

CONF_ENGINE: Final = "engine"
CONF_VOICE: Final = "voice"
CONF_OUTPUT_FORMAT: Final = "output_format"
CONF_SAMPLE_RATE: Final = "sample_rate"
CONF_TEXT_TYPE: Final = "text_type"

SUPPORTED_VOICES: Final[list[str]] = [
    "Aditi",  # Indian English
    "Adriano",  # Italian
    "Amy",  # British English
    "Andrés",  # Mexican Spanish
    "Aria",  # New Zealand English
    "Arlet",  # Catalan
    "Arthur",  # British English
    "Astrid",  # Swedish
    "Ayanda",  # South African English
    "Bianca",  # Italian
    "Brian",  # British English
    "Burcu",  # Turkish
    "Céline",  # French
    "Camila",  # Brazilian Portuguese
    "Carla",  # Italian
    "Carmen",  # Romanian
    "Chantal",  # Canadian French
    "Conchita",  # Castilian Spanish
    "Cristiano",  # Portuguese
    "Dóra",  # Icelandic
    "Daniel",  # German
    "Danielle",  # US English
    "Elin",  # Swedish
    "Emma",  # British English
    "Enrique",  # Castilian Spanish
    "Ewa",  # Polish
    "Filiz",  # Turkish
    "Gabrielle",  # Canadian French
    "Geraint",  # Welsh English
    "Giorgio",  # Italian
    "Gregory",  # US English
    "Gwyneth",  # Welsh
    "Hala",  # Gulf Arabic
    "Hannah",  # Austrian German
    "Hans",  # German
    "Hiujin",  # Cantonese
    "Ida",  # Norwegian
    "Inês",  # Portuguese
    "Isabelle",  # Belgian French
    "Ivy",  # US English
    "Jacek",  # Polish
    "Jan",  # Polish
    "Joanna",  # US English
    "Joey",  # US English
    "Justin",  # US English
    "Kajal",  # Indian English
    "Karl",  # Icelandic
    "Kazuha",  # Japanese
    "Kendra",  # US English
    "Kevin",  # US English
    "Kimberly",  # US English
    "Léa",  # French
    "Laura",  # Dutch
    "Liam",  # Canadian French
    "Lisa",  # Belgian Dutch
    "Liv",  # Norwegian
    "Lotte",  # Dutch
    "Lucia",  # Castilian Spanish
    "Lupe",  # US Spanish
    "Mads",  # Danish
    "Maja",  # Polish
    "Marlene",  # German
    "Mathieu",  # French
    "Matthew",  # US English
    "Maxim",  # Russian
    "Mia",  # Mexican Spanish
    "Miguel",  # US Spanish
    "Mizuki",  # Japanese
    "Naja",  # Danish
    "Niamh",  # Irish English
    "Nicole",  # Australian English
    "Ola",  # Polish
    "Olivia",  # Australian English
    "Pedro",  # US Spanish
    "Penélope",  # US Spanish
    "Rémi",  # French
    "Raveena",  # Indian English
    "Ricardo",  # Brazilian Portuguese
    "Ruben",  # Dutch
    "Russell",  # Australian English
    "Ruth",  # US English
    "Salli",  # US English
    "Seoyeon",  # Korean
    "Sergio",  # Castilian Spanish
    "Sofie",  # Danish
    "Stephen",  # US English
    "Suvi",  # Finnish
    "Takumi",  # Japanese
    "Tatyana",  # Russian
    "Thiago",  # Brazilian Portuguese
    "Tomoko",  # Japanese
    "Vicki",  # German
    "Vitória",  # Brazilian Portuguese
    "Zayd",  # Gulf Arabic
    "Zeina",  # Arabic
    "Zhiyu",  # Chinese Mandarin
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
