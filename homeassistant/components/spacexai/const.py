"""Constants for the SpaceXAI integration."""

from logging import Logger, getLogger

DOMAIN = "spacexai"
LOGGER: Logger = getLogger(__package__)

AUTHORIZE_URL = "https://auth.x.ai/oauth2/authorize"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
USERINFO_URL = "https://auth.x.ai/oauth2/userinfo"
REVOCATION_URL = "https://auth.x.ai/oauth2/revoke"
API_BASE_URL = "https://api.x.ai/v1"

OAUTH_SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    "grok-cli:access",
    "api:access",
)

CONF_MAX_OUTPUT_TOKENS = "max_output_tokens"

ISSUE_MODEL_NOT_ENTITLED = "model_not_entitled"
ISSUE_SUBSCRIPTION_NOT_ENTITLED = "subscription_not_entitled"

DEFAULT_CONVERSATION_NAME = "Grok"
DEFAULT_MAX_OUTPUT_TOKENS = 2048
DEFAULT_MODEL = "grok-4.5"
DEFAULT_MODEL_PLACEHOLDER = "Grok"
HTTP_TIMEOUT_SECONDS = 30
MAX_TOOL_ITERATIONS = 10
CREATE_TIMEOUT = 30
RESPONSE_TIMEOUT = 300
CONVERSE_TIMEOUT = 600
