"""Constants for the OpenAI Conversation integration."""

DOMAIN = "openai_conversation"
CONF_PROMPT = "prompt"
DEFAULT_MODEL = "text-davinci-003"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

An overview of the areas and the devices in this smart home:
{%- for area_id in matched_areas %}
  {%- set area_info = namespace(printed=false) %}
  {%- for device in area_devices(area_id) -%}
    {%- if not device_attr(device, "disabled_by") and not device_attr(device, "entry_type") %}
      {%- if not area_info.printed %}

{{ area_name(area_id) }}:
        {%- set area_info.printed = true %}
      {%- endif %}
- {{ device_attr(device, "name") }}{% if device_attr(device, "model") and device_attr(device, "model") not in device_attr(device, "name") %} ({{ device_attr(device, "model") }}){% endif %}
    {%- endif %}
{%- endfor %}
{%- endfor %}

Answer the users questions about the world truthfully.

If the user wants to control a device, reject the request and suggest using the Home Assistant app.

Now finish this conversation:

Smart home: How can I assist?
"""
DEFAULT_CONTINUED_PROMPT = ""
CONF_PROMPT = "prompt"
CONF_CONTINUED_PROMPT = "continued_prompt"
CONF_ENGINE = "engine"
CONF_MAX_TOKENS = "max_tokens"
CONF_TOP_P = "top_p"
CONF_TEMPERATURE = "temperature"
DEFAULT_ENGINE = "text-davinci-003"
DEFAULT_MAX_TOKENS = 150
DEFAULT_TOP_P = 1
DEFAULT_TEMPERATURE = 0.5
