"""Constants for the Ollama integration."""

DOMAIN = "ollama"

CONF_MODEL = "model"
CONF_PROMPT = "prompt"

TOOL_CALL = "TOOL_CALL"
TOOL_ARGS = "TOOL_ARGS"
TOOLS_PROMPT = (
    "There are certain tools (functions) that you can call (execute)"
    " and get the result before answering to the user. You can either call a tool or"
    """ respond to the user in one response.
To call the tool, start the response with TOOL_CALL followed by tool name and"""
    ' parameters in json format, example: TOOL_CALL {"name": "tool_name", "parameters":'
    """ {\"arg\": 42}}
Respond with TOOL_ARGS followed by the tool name without quotes to get the available"""
    """ tool args in JSON object schema format. Always do it before calling the tool.
Available tools:"""
)

CONF_KEEP_ALIVE = "keep_alive"
DEFAULT_KEEP_ALIVE = -1  # seconds. -1 = indefinite, 0 = never

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
