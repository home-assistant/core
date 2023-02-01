"""Constants for the OpenAI Conversation integration."""

DOMAIN = "openai_conversation"
CONF_PROMPT = "prompt"
DEFAULT_MODEL = "text-davinci-003"
DEFAULT_PROMPT = """This smart home is controlled by Home Assistant.

An overview of the areas and the devices in this smart home:
{%- for area in areas %}
  {%- set area_info = namespace(printed=false) %}
  {%- for device in area_devices(area.name) -%}
    {%- if not device_attr(device, "disabled_by") and not device_attr(device, "entry_type") %}
      {%- if not area_info.printed %}

{{ area.name }}:
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
