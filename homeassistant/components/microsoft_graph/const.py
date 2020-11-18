"""Constants for the Microsoft Graph integration."""

DOMAIN = "microsoft_graph"

# TODO Update with your own urls
OAUTH2_AUTHORIZE = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
OAUTH2_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

DEFAULT_SCOPES = ["https://graph.microsoft.com/.default", "offline_access"]