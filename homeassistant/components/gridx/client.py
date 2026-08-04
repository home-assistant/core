"""Client helpers for the GridX integration."""

from typing import Any

from gridx_connector.async_connector import AsyncGridboxConnector
import httpx

from .const import (
    LOGGER,
    LOGIN_AUDIENCE,
    LOGIN_CLIENT_ID,
    LOGIN_GRANT_TYPE,
    LOGIN_REALM,
    LOGIN_SCOPE,
    LOGIN_URL,
)


def build_connector_config(username: str, password: str) -> dict[str, Any]:
    """Build the connector endpoint config for the given credentials."""
    return {
        "urls": {"login": LOGIN_URL},
        "login": {
            "grant_type": LOGIN_GRANT_TYPE,
            "username": username,
            "password": password,
            "audience": LOGIN_AUDIENCE,
            "client_id": LOGIN_CLIENT_ID,
            "scope": LOGIN_SCOPE,
            "realm": LOGIN_REALM,
            "client_secret": "",
        },
    }


async def async_create_connector(
    config: dict[str, Any],
    httpx_client: httpx.AsyncClient,
) -> AsyncGridboxConnector:
    """Create and initialize a GridX connector."""
    return await AsyncGridboxConnector.create(
        config,
        logger=LOGGER,
        httpx_client=httpx_client,
        owns_httpx_client=True,
    )
