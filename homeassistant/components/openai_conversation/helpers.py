"""Helper functions for the OpenAI Conversation integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl

import openai

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_API_BASE, CONF_DEFAULT_QUERY


def parse_default_query(query_string: str) -> dict[str, str]:
    """Parse a query string like 'api-version=preview&foo=bar' into a dict."""
    if not query_string:
        return {}
    return dict(parse_qsl(query_string.strip(), keep_blank_values=True))


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> openai.AsyncOpenAI:
    """Create an OpenAI client from config entry data."""
    client_kwargs: dict[str, Any] = {
        "api_key": data[CONF_API_KEY],
        "http_client": get_async_client(hass),
    }

    if api_base := data.get(CONF_API_BASE):
        client_kwargs["base_url"] = api_base

    if default_query := data.get(CONF_DEFAULT_QUERY):
        client_kwargs["default_query"] = parse_default_query(default_query)

    return openai.AsyncOpenAI(**client_kwargs)
