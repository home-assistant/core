"""Constants for the Ollama integration."""

DOMAIN = "ollama"

CONF_MODEL = "model"
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """{%- set used_domains = set([
  "binary_sensor",
  "climate",
  "cover",
  "fan",
  "light",
  "lock",
  "sensor",
  "switch",
  "weather",
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
DEFAULT_MAX_HISTORY = 20

MAX_HISTORY_SECONDS = 60 * 60  # 1 hour

MODEL_NAMES = [  # https://ollama.com/library
    "gemma",
    "llama2",
    "mistral",
    "mixtral",
    "llava",
    "neural-chat",
    "codellama",
    "dolphin-mixtral",
    "qwen",
    "llama2-uncensored",
    "mistral-openorca",
    "deepseek-coder",
    "nous-hermes2",
    "phi",
    "orca-mini",
    "dolphin-mistral",
    "wizard-vicuna-uncensored",
    "vicuna",
    "tinydolphin",
    "llama2-chinese",
    "nomic-embed-text",
    "openhermes",
    "zephyr",
    "tinyllama",
    "openchat",
    "wizardcoder",
    "starcoder",
    "phind-codellama",
    "starcoder2",
    "yi",
    "orca2",
    "falcon",
    "wizard-math",
    "dolphin-phi",
    "starling-lm",
    "nous-hermes",
    "stable-code",
    "medllama2",
    "bakllava",
    "codeup",
    "wizardlm-uncensored",
    "solar",
    "everythinglm",
    "sqlcoder",
    "dolphincoder",
    "nous-hermes2-mixtral",
    "stable-beluga",
    "yarn-mistral",
    "stablelm2",
    "samantha-mistral",
    "meditron",
    "stablelm-zephyr",
    "magicoder",
    "yarn-llama2",
    "llama-pro",
    "deepseek-llm",
    "wizard-vicuna",
    "codebooga",
    "mistrallite",
    "all-minilm",
    "nexusraven",
    "open-orca-platypus2",
    "goliath",
    "notux",
    "megadolphin",
    "alfred",
    "xwinlm",
    "wizardlm",
    "duckdb-nsql",
    "notus",
]
DEFAULT_MODEL = "llama2:latest"
