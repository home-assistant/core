"""Azure OpenAI client configuration."""

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

import openai

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_BASE_URL

_AZURE_HOST_SUFFIXES = (
    ".openai.azure.com",
    ".openai.azure.us",
    ".openai.azure.cn",
    ".cognitiveservices.azure.com",
    ".services.ai.azure.com",
)


def normalize_base_url(base_url: str) -> str:
    """Append the v1 path only to recognized bare Azure resource endpoints."""
    base_url = base_url.strip()
    parsed = urlparse(base_url)
    if parsed.scheme and parsed.netloc and parsed.hostname is not None:
        hostname = parsed.hostname.lower()
        if hostname.endswith(_AZURE_HOST_SUFFIXES):
            parsed = parsed._replace(netloc=parsed.netloc.lower())
            if parsed.path in ("", "/", "/openai/v1", "/openai/v1/"):
                parsed = parsed._replace(path="/openai/v1/", query="", fragment="")
            return parsed.geturl()
    return base_url


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> openai.AsyncOpenAI:
    """Construct a client with the same connection settings for every API call.

    Azure's v1 API rejects an api-version query parameter, so one is never
    added here. Only the classic per-deployment transport (see
    create_classic_deployment_client) still needs api-version, and it is
    scoped to that specific call instead of the shared connection.
    """
    return openai.AsyncOpenAI(
        api_key=data[CONF_API_KEY],
        base_url=normalize_base_url(data[CONF_BASE_URL]),
        # Legacy HTTPX clients are supported at runtime only.
        http_client=cast(Any, get_async_client(hass)),
    )


def create_classic_deployment_client(
    hass: HomeAssistant, data: Mapping[str, Any], deployment: str, api_version: str
) -> openai.AsyncAzureOpenAI:
    """Build a client scoped to one deployment's classic (non-v1) path.

    Speech-to-text is not reachable through the shared v1 client and requires the older
    /openai/deployments/{deployment}/... request shape and its own
    api-version, regardless of the api_version configured for the v1 client.
    """
    parsed = urlparse(data[CONF_BASE_URL].strip())
    path = parsed.path.rstrip("/").removesuffix("/openai/v1")
    endpoint = parsed._replace(path=path, query="", fragment="").geturl()
    return openai.AsyncAzureOpenAI(
        api_key=data[CONF_API_KEY],
        api_version=api_version,
        azure_deployment=deployment,
        azure_endpoint=endpoint,
        # Legacy HTTPX clients are supported at runtime only.
        http_client=cast(Any, get_async_client(hass)),
    )
