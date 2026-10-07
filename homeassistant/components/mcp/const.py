"""Constants for the Model Context Protocol integration."""

from typing import Literal

DOMAIN = "mcp"

CONF_AUTHORIZATION_URL = "authorization_url"
CONF_TOKEN_URL = "token_url"
CONF_SCOPE = "scope"
CONF_SLUG = "slug"

# Shown on the authorization server and in Application Credentials.
DCR_CLIENT_NAME = "Home Assistant"

TOKEN_ENDPOINT_AUTH_NONE = "none"
TOKEN_ENDPOINT_AUTH_POST = "client_secret_post"
TOKEN_ENDPOINT_AUTH_BASIC = "client_secret_basic"

type TokenEndpointAuthMethod = Literal[
    "none",
    "client_secret_post",
    "client_secret_basic",
]

# Public clients first: MCP clients register with PKCE when the server allows it.
SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS: tuple[TokenEndpointAuthMethod, ...] = (
    TOKEN_ENDPOINT_AUTH_NONE,
    TOKEN_ENDPOINT_AUTH_POST,
    TOKEN_ENDPOINT_AUTH_BASIC,
)
