"""Constants for the SpaceXSI integration."""

from spacexai_subscription_client.const import GROK_CLI_OAUTH_CLIENT_ID

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm
from homeassistant.util import slugify

DOMAIN = "spacexsi"
# Match the stored credential ID so Home Assistant protects it while in use.
AUTH_IMPLEMENTATION = slugify(f"{DOMAIN}.{GROK_CLI_OAUTH_CLIENT_ID}")

DEFAULT_CONVERSATION_NAME = "Grok"
MAX_TOOL_ITERATIONS = 10

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
