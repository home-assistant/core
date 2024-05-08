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
    "alfred",
    "all-minilm",
    "bakllava",
    "codebooga",
    "codegemma",
    "codellama",
    "codeqwen",
    "codeup",
    "command-r",
    "command-r-plus",
    "dbrx",
    "deepseek-coder",
    "deepseek-llm",
    "dolphin-llama3",
    "dolphin-mistral",
    "dolphin-mixtral",
    "dolphin-phi",
    "dolphincoder",
    "duckdb-nsql",
    "everythinglm",
    "falcon",
    "gemma",
    "goliath",
    "llama-pro",
    "llama2",
    "llama2-chinese",
    "llama2-uncensored",
    "llama3",
    "llava",
    "magicoder",
    "meditron",
    "medllama2",
    "megadolphin",
    "mistral",
    "mistral-openorca",
    "mistrallite",
    "mixtral",
    "mxbai-embed-large",
    "neural-chat",
    "nexusraven",
    "nomic-embed-text",
    "notus",
    "notux",
    "nous-hermes",
    "nous-hermes2",
    "nous-hermes2-mixtral",
    "open-orca-platypus2",
    "openchat",
    "openhermes",
    "orca-mini",
    "orca2",
    "phi",
    "phi3",
    "phind-codellama",
    "qwen",
    "samantha-mistral",
    "snowflake-arctic-embed",
    "solar",
    "sqlcoder",
    "stable-beluga",
    "stable-code",
    "stablelm-zephyr",
    "stablelm2",
    "starcoder",
    "starcoder2",
    "starling-lm",
    "tinydolphin",
    "tinyllama",
    "vicuna",
    "wizard-math",
    "wizard-vicuna",
    "wizard-vicuna-uncensored",
    "wizardcoder",
    "wizardlm",
    "wizardlm-uncensored",
    "wizardlm2",
    "xwinlm",
    "yarn-llama2",
    "yarn-mistral",
    "yi",
    "zephyr",
]
DEFAULT_MODEL = "llama2:latest"
