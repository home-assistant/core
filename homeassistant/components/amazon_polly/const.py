"""Constants for the Amazon Polly text to speech service."""
import typing

CONF_REGION: typing.Final = "region_name"
CONF_ACCESS_KEY_ID: typing.Final = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY: typing.Final = "aws_secret_access_key"

DEFAULT_REGION: typing.Final = "us-east-1"
SUPPORTED_REGIONS: typing.Final[list[str]] = [
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

CONF_ENGINE: typing.Final = "engine"
CONF_VOICE: typing.Final = "voice"
CONF_OUTPUT_FORMAT: typing.Final = "output_format"
CONF_SAMPLE_RATE: typing.Final = "sample_rate"
CONF_TEXT_TYPE: typing.Final = "text_type"

SUPPORTED_VOICES: typing.Final[list[str]] = [
    "Aditi",  # Hindi
    "Amy",
    "Aria",
    "Astrid",  # Swedish
    "Ayanda",
    "Bianca",  # Italian
    "Brian",
    "Camila",  # Portuguese, Brazilian
    "Carla",
    "Carmen",  # Romanian
    "Celine",
    "Chantal",  # French Canadian
    "Conchita",
    "Cristiano",
    "Dora",  # Icelandic
    "Emma",  # English
    "Enrique",
    "Ewa",
    "Filiz",  # Turkish
    "Gabrielle",
    "Geraint",  # English Welsh
    "Giorgio",
    "Gwyneth",  # Welsh
    "Hans",
    "Ines",  # Portuguese, European
    "Ivy",
    "Jacek",
    "Jan",
    "Joanna",
    "Joey",
    "Justin",
    "Karl",
    "Kendra",
    "Kevin",
    "Kimberly",
    "Lea",  # French
    "Liv",  # Norwegian
    "Lotte",  # Dutch
    "Lucia",  # Spanish European
    "Lupe",  # Spanish US
    "Mads",
    "Maja",  # Polish
    "Marlene",
    "Mathieu",
    "Matthew",
    "Maxim",
    "Mia",  # Spanish Mexican
    "Miguel",  # Spanish US
    "Mizuki",  # Japanese
    "Naja",  # Danish
    "Nicole",  # English Australian
    "Olivia",  # Female, Australian, Neural
    "Penelope",  # Spanish US
    "Raveena",  # English, Indian
    "Ricardo",
    "Ruben",
    "Russell",
    "Salli",  # English
    "Seoyeon",  # Korean
    "Takumi",
    "Tatyana",  # Russian
    "Vicki",  # German
    "Vitoria",  # Portuguese, Brazilian
    "Zeina",
    "Zhiyu",  # Chinese
]

SUPPORTED_OUTPUT_FORMATS: typing.Final[list[str]] = ["mp3", "ogg_vorbis", "pcm"]

SUPPORTED_ENGINES: typing.Final[list[str]] = ["neural", "standard"]

SUPPORTED_SAMPLE_RATES: typing.Final[list[str]] = ["8000", "16000", "22050", "24000"]

SUPPORTED_SAMPLE_RATES_MAP: typing.Final[dict[str, list[str]]] = {
    "mp3": ["8000", "16000", "22050", "24000"],
    "ogg_vorbis": ["8000", "16000", "22050"],
    "pcm": ["8000", "16000"],
}

SUPPORTED_TEXT_TYPES: typing.Final[list[str]] = ["text", "ssml"]

CONTENT_TYPE_EXTENSIONS: typing.Final[dict[str, str]] = {
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/pcm": "pcm",
}

DEFAULT_ENGINE: typing.Final = "standard"
DEFAULT_VOICE: typing.Final = "Joanna"
DEFAULT_OUTPUT_FORMAT: typing.Final = "mp3"
DEFAULT_TEXT_TYPE: typing.Final = "text"

DEFAULT_SAMPLE_RATES: typing.Final[dict[str, str]] = {
    "mp3": "22050",
    "ogg_vorbis": "22050",
    "pcm": "16000",
}

CONF_CONFIG: typing.Final = "config"
AWS_CONF_CONNECT_TIMEOUT: typing.Final = 10
AWS_CONF_READ_TIMEOUT: typing.Final = 5
AWS_CONF_MAX_POOL_CONNECTIONS: typing.Final = 1
