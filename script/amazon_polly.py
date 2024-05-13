"""Helper script to update supported languages for Amazone Polly text-to-speech (TTS)."""

from pathlib import Path

import boto3
from pydantic import BaseModel, Field

from .hassfest.serializer import format_python_namespace


class AmazonPollyVoice(BaseModel):
    """Amazon Polly Voice."""

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    gender: str = Field(alias="Gender")
    language_name: str = Field(alias="LanguageName")
    language_code: str = Field(alias="LanguageCode")
    supported_engines: set[str] = Field(alias="SupportedEngines")
    additional_language_codes: set[str] = Field(
        default=set(), alias="AdditionalLanguageCodes"
    )


def get_all_voices(client: boto3.client) -> list[AmazonPollyVoice]:
    """Get list of all supported voices from Amazon Polly."""
    response = client.describe_voices()
    return [AmazonPollyVoice.validate(voice) for voice in response["Voices"]]


supported_regions = sorted(
    boto3.session.Session().get_available_regions(service_name="polly")
)

polly_client = boto3.client(service_name="polly", region_name="us-east-1")
voices = get_all_voices(polly_client)
supported_voices = sorted([v.id for v in voices])

Path("homeassistant/generated/amazon_polly.py").write_text(
    format_python_namespace(
        {
            "SUPPORTED_VOICES": supported_voices,
            "SUPPORTED_REGIONS": supported_regions,
        },
        annotations={
            "SUPPORTED_VOICES": "list[str]",
            "SUPPORTED_REGIONS": "list[str]",
        },
        generator="script.amazon_polly",
    )
)
