"""Get all supported voices from Amazon Polly."""

import boto3
from pydantic import BaseModel, Field


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


if __name__ == "__main__":
    client = boto3.client("polly")
    voices = get_all_voices(client)
    for voice in sorted(voices, key=lambda x: x.id):
        print(  # noqa: T201
            f'"{voice.id}", # {voice.language_name} ({voice.language_code})'
        )
