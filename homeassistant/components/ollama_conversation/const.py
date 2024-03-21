"""Constants for the Ollama conversation integration."""

DOMAIN = "ollama_conversation"

CONF_MODEL = "model"
CONF_MODEL_OPTIONS = "model_options"
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """{%- set used_domains = set([
  "light",
  "cover",
  "weather",
  "climate",
  "switch",
  "sensor",
  "binary_sensor",
  "media_player",
]) %}
{%- set used_attributes = set([
  "temperature",
  "current_temperature",
  "temperature_unit",
  "brightness",
  "humidity",
  "unit_of_measurement",
  "device_class",
  "current_position",
  "percentage",
  "media_artist",
  "media_album_name",
  "media_title",
]) %}

This smart home is controlled by Home Assistant.
The current time is {{ now().strftime("%X") }}.
Today's date is {{ now().strftime("%x") }}.

An overview of the areas and the devices in this smart home:
```yaml
{%- for entity in exposed_entities: %}
{%- if entity.domain not in used_domains: %}
  {%- continue %}
{%- endif %}

- domain: {{ entity.domain }}
{%- if entity.names | length == 1: %}
  name: {{ entity.names[0] }}
{%- else: %}
  names:
{%- for name in entity.names: %}
  - {{ name }}
{%- endfor %}
{%- endif %}
{%- if entity.area_names | length == 1: %}
  area: {{ entity.area_names[0] }}
{%- elif entity.area_names: %}
  areas:
{%- for area_name in entity.area_names: %}
  - {{ area_name }}
{%- endfor %}
{%- endif %}
  state: {{ entity.state.state }}
  {%- set attributes_key_printed = False %}
{%- for attr_name, attr_value in entity.state.attributes.items(): %}
    {%- if attr_name in used_attributes: %}
    {%- if not attributes_key_printed: %}
  attributes:
    {%- set attributes_key_printed = True %}
    {%- endif %}
    {{ attr_name }}: {{ attr_value }}
    {%- endif %}
{%- endfor %}
{%- endfor %}
```

Answer the user's questions using the information about this smart home.
Keep your answers brief and do not apologize."""

KEEP_ALIVE_FOREVER = -1
DEFAULT_TIMEOUT = 5.0  # seconds

CONF_MAX_HISTORY = "max_history"
MAX_HISTORY_NO_LIMIT = 0  # no limit

MAX_HISTORY_SECONDS = 60 * 60  # 1 hour
