"""Helper script to update supported languages for Amazone Polly text-to-speech (TTS).

N.B. This script requires AWS credentials.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self

import boto3

from .hassfest.serializer import format_python_namespace


@dataclass(frozen=True)
class AmazonPollyVoice:
    """Amazon Polly Voice."""

    id: str
    name: str
    gender: str
    language_name: str
    language_code: str
    supported_engines: set[str]
    additional_language_codes: set[str]

    @classmethod
    def validate(cls, model: dict[str, str | list[str]]) -> Self:
        """Validate data model."""
        return cls(
            id=model["Id"],
            name=model["Name"],
            gender=model["Gender"],
            language_name=model["LanguageName"],
            language_code=model["LanguageCode"],
            supported_engines=set(model["SupportedEngines"]),
            additional_language_codes=set(model.get("AdditionalLanguageCodes", [])),
        )


def get_all_voices(client: boto3.client) -> list[AmazonPollyVoice]:
    """Get list of all supported voices from Amazon Polly."""
    response = client.describe_voices()
    return [AmazonPollyVoice.validate(voice) for voice in response["Voices"]]


supported_regions = set(
    boto3.session.Session().get_available_regions(service_name="polly")
)

polly_client = boto3.client(service_name="polly", region_name="us-east-1")
voices = get_all_voices(polly_client)
supported_voices = set({v.id for v in voices})
supported_engines = set().union(*[v.supported_engines for v in voices])

Path("homeassistant/generated/amazon_polly.py").write_text(
    format_python_namespace(
        {
            "SUPPORTED_VOICES": supported_voices,
            "SUPPORTED_REGIONS": supported_regions,
            "SUPPORTED_ENGINES": supported_engines,
        },
        annotations={
            "SUPPORTED_VOICES": "Final[set[str]]",
            "SUPPORTED_REGIONS": "Final[set[str]]",
            "SUPPORTED_ENGINES": "Final[set[str]]",
        },
        generator="script.amazon_polly",
    )
)
