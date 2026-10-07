"""Constants for the Model Context Protocol integration."""

from typing import Final, Literal

DOMAIN = "mcp"

# Shown on the authorization server and in Application Credentials.
DCR_CLIENT_NAME = "Home Assistant"

TOKEN_ENDPOINT_AUTH_NONE: Final = "none"
TOKEN_ENDPOINT_AUTH_POST: Final = "client_secret_post"
TOKEN_ENDPOINT_AUTH_BASIC: Final = "client_secret_basic"

type TokenEndpointAuthMethod = Literal[
    "none",
    "client_secret_post",
    "client_secret_basic",
]

CONF_AUTHORIZATION_URL = "authorization_url"
CONF_TOKEN_URL = "token_url"
CONF_SCOPE = "scope"
CONF_SLUG = "slug"
