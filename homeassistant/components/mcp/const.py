"""Constants for the Model Context Protocol integration."""

DOMAIN = "mcp"

# The apex host redirects to www. The metadata document must be fetched
# directly, so the client id is the www URL.
CIMD_CLIENT_ID = "https://www.home-assistant.io/mcp/oauth-client.json"
CIMD_AUTH_IMPLEMENTATION = "mcp_client_metadata"

CONF_AUTHORIZATION_URL = "authorization_url"
CONF_TOKEN_URL = "token_url"
CONF_SCOPE = "scope"
CONF_SLUG = "slug"
