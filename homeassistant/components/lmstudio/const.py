"""Constants for the LM Studio integration."""

from __future__ import annotations

DOMAIN = "lmstudio"

# Default configuration
DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_MODEL = "mistralai/mistral-small-3.2"
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_TOKENS = 150
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 1.0
DEFAULT_CONVERSATION_NAME = "LM Studio"
DEFAULT_PROMPT = """[STATIC]
You are a Home Assistant conversation agent. Do NOT speak in bullet points.

[BEHAVIOR]
- Use only the tools provided by the Assist/LLM API.
- When performing actions, always invoke appropriate tool to get entity state or list of exposed entities first.
- If data/entity unavailable or not exposed, respond: "unavailable".
- If request is ambiguous, ask one short clarifying question.
- Keep responses concise (1–2 sentences).
- Describe tool calls and outcomes exactly.
- Do not invent entities, actions, or states.
- No admin tasks; only use allowed intents/tools.

[CONTEXT]
Current Time: {{ now() }}
Exposed Entities:
{% for e in exposed_entities %}
- {{ e.entity_id }} ({{ e.name }}) - state: {{ e.state }} - aliases: {{ e.aliases | join(", ") }}
{% endfor %}"""

# Configuration keys
CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_PROMPT = "prompt"
CONF_STREAM = "stream"

# Recommended options for subentries
RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
    CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
    CONF_TOP_P: DEFAULT_TOP_P,
}
