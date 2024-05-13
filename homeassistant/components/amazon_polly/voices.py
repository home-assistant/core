"""Get all supported voices from Amazon Polly"""

import boto3
from pydantic import BaseModel, Field


class AmazonPollyVoice(BaseModel):
    id: str = Field(None, alias="Id")
    name: str = Field(None, alias="Name")
    gender: str = Field(None, alias="Gender")
    language_name: str = Field(None, alias="LanguageName")
    language_code: str = Field(None, alias="LanguageCode")
    supported_engines: set[str] = Field(None, alias="SupportedEngines")


def get_all_voices(client: boto3.client) -> list[AmazonPollyVoice]:
    response = client.describe_voices()
    return [AmazonPollyVoice.validate(voice) for voice in response["Voices"]]


def main() -> None:
    client = boto3.client("polly")
    voices = get_all_voices(client)
    for voice in sorted(voices, key=lambda x: x.id):
        print(f'"{voice.id}", # {voice.language_name} ({voice.language_code})')


if __name__ == "__main__":
    main()
