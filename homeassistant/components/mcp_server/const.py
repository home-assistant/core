"""Constants for the Model Context Protocol Server integration."""

DOMAIN = "mcp_server"
TITLE = "Model Context Protocol Server"
# The Stateless API is no longer registered explicitly, but this name may still
# exist in the user's config entry for backwards compatibility.
STATELESS_LLM_API = "stateless_assist"

SSE_API = f"/{DOMAIN}/sse"
MESSAGES_API = f"/{DOMAIN}/messages/{{session_id}}"
STREAMABLE_HTTP_API = f"/{DOMAIN}/mcp"
