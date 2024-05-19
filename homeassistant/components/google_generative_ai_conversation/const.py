"""Constants for the Google Generative AI Conversation integration."""

import logging

DOMAIN = "google_generative_ai_conversation"
LOGGER = logging.getLogger(__package__)
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

An overview of the areas and the devices in this smart home:
{%- for area in areas() %}
  {%- set area_info = namespace(printed=false) %}
  {%- for device in area_devices(area) -%}
    {%- if not device_attr(device, "disabled_by") and not device_attr(device, "entry_type") and device_attr(device, "name") %}
      {%- if not area_info.printed %}

{{ area_name(area) }}:
        {%- set area_info.printed = true %}
      {%- endif %}
- {{ device_attr(device, "name") }}{% if device_attr(device, "model") and (device_attr(device, "model") | string) not in (device_attr(device, "name") | string) %} ({{ device_attr(device, "model") }}){% endif %}
    {%- endif %}
  {%- endfor %}
{%- endfor %}
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
DEFAULT_MAX_TOKENS = 150
DEFAULT_ALLOW_HASS_ACCESS = False
