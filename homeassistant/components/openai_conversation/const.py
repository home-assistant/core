"""Constants for the OpenAI Conversation integration."""

import logging

DOMAIN = "openai_conversation"
LOGGER = logging.getLogger(__package__)
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

There are following areas in this smart home:
{%- for area in areas() %} {{area_name(area)}}{{ "," if not loop.last else "" }}{%- endfor %}.

Answer the user's questions about the world truthfully.

The response may be used in Text-to-Speech synthesizers, so prefer shorter responses that are optimized to be spoken.
"""
CONF_CHAT_MODEL = "chat_model"
DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
CONF_MAX_TOKENS = "max_tokens"
DEFAULT_MAX_TOKENS = 256
CONF_TOP_P = "top_p"
DEFAULT_TOP_P = 1
CONF_TEMPERATURE = "temperature"
DEFAULT_TEMPERATURE = 0.5
