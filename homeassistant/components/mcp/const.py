"""Constants for the Model Context Protocol integration."""

DOMAIN = "mcp"

CONF_AUTHORIZATION_URL = "authorization_url"
CONF_TOKEN_URL = "token_url"
CONF_SCOPE = "scope"
CONF_SLUG = "slug"
CONF_SERVER_NAME = "server_name"

# Providers such as OpenAI and Anthropic reject tool names longer than this
MAX_TOOL_NAME_LENGTH = 64
MAX_NAMESPACE_LENGTH = 24
