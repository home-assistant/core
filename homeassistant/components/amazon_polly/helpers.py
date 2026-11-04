"""Helpers for the Amazon Polly integration."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Final

from aiobotocore.client import AioBaseClient
from aiobotocore.config import AioConfig
from aiobotocore.session import AioSession
from botocore.exceptions import BotoCoreError, ClientError

from homeassistant.core import HomeAssistant

from .const import (
    AWS_CONF_CONNECT_TIMEOUT,
    AWS_CONF_MAX_POOL_CONNECTIONS,
    AWS_CONF_READ_TIMEOUT,
)

AUTH_ERROR_CODES: Final[set[str]] = {
    "AccessDeniedException",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "InvalidSignatureException",
    "SignatureDoesNotMatch",
    "UnrecognizedClientException",
}


class CannotConnect(Exception):
    """Error to indicate Amazon Polly cannot be reached."""


class InvalidAuth(Exception):
    """Error to indicate the AWS credentials were rejected."""


@dataclass
class AmazonPollyData:
    """Connected Amazon Polly client and the voices it offers."""

    client: AioBaseClient
    voices: dict[str, dict[str, Any]] = field(default_factory=dict)
    languages: list[str] = field(default_factory=list)
    engines: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def _create_session(profile: str | None) -> AioSession:
    """Create a session with its AWS config files already read."""
    session = AioSession(profile=profile)
    session.get_scoped_config()
    return session


async def async_connect(
    hass: HomeAssistant,
    *,
    region: str,
    access_key_id: str | None,
    secret_access_key: str | None,
    profile: str | None = None,
) -> AmazonPollyData:
    """Create a Polly client and load the available voices.

    The caller owns the returned client and must close it.
    """
    session = await hass.async_add_executor_job(_create_session, profile)
    # pylint: disable-next=unnecessary-dunder-call
    client: AioBaseClient = await session.create_client(
        "polly",
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=AioConfig(
            connect_timeout=AWS_CONF_CONNECT_TIMEOUT,
            read_timeout=AWS_CONF_READ_TIMEOUT,
            max_pool_connections=AWS_CONF_MAX_POOL_CONNECTIONS,
            warm_up_loader_caches=True,
        ),
    ).__aenter__()
    data = AmazonPollyData(client=client)
    try:
        await _async_load_voices(data)
    except ClientError as err:
        await client.__aexit__(None, None, None)
        if err.response.get("Error", {}).get("Code") in AUTH_ERROR_CODES:
            raise InvalidAuth(str(err)) from err
        raise CannotConnect(str(err)) from err
    except BotoCoreError as err:
        await client.__aexit__(None, None, None)
        raise CannotConnect(str(err)) from err
    return data


async def _async_load_voices(data: AmazonPollyData) -> None:
    """Fill in the voices, languages and engines Polly offers."""
    kwargs: dict[str, str] = {}
    while True:
        response = await data.client.describe_voices(**kwargs)
        for voice in response.get("Voices", []):
            voice_id = voice["Id"]
            data.voices[voice_id] = voice
            language_code = voice.get("LanguageCode")
            if language_code is not None and language_code not in data.languages:
                data.languages.append(language_code)
            for engine in voice.get("SupportedEngines", []):
                data.engines[engine].add(voice_id)
        if not (next_token := response.get("NextToken")):
            return
        kwargs["NextToken"] = next_token
