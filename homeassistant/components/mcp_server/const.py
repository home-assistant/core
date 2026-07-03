"""Constants for the Model Context Protocol Server integration."""

DOMAIN = "mcp_server"
TITLE = "Model Context Protocol Server"
# The Stateless API is no longer registered explicitly, but this
# name may still exist in the users config entry.
STATELESS_LLM_API = "stateless_assist"

# Marks a config entry that predates multiple config entry support. Legacy
# entries remain served on the original fixed URLs for backwards compatibility.
CONF_LEGACY = "legacy"

# The URL identifier for a non-legacy config entry. It is generated when the
# entry is created and stays stable so client URLs do not change.
CONF_URL_ID = "url_id"
