"""Constants for the Google Generative AI Conversation integration."""

DOMAIN = "google_generative_ai_conversation"
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

There are following areas in this smart home:
{%- for area in areas() %} {{area_name(area)}}{{ "," if not loop.last else "" }}{%- endfor %}.

Answer the user's questions about the world truthfully.
"""
CONF_CHAT_MODEL = "chat_model"
DEFAULT_CHAT_MODEL = "models/gemini-pro"
CONF_TEMPERATURE = "temperature"
DEFAULT_TEMPERATURE = 0.9
CONF_TOP_P = "top_p"
DEFAULT_TOP_P = 1.0
CONF_TOP_K = "top_k"
DEFAULT_TOP_K = 1
CONF_MAX_TOKENS = "max_tokens"
DEFAULT_MAX_TOKENS = 256
