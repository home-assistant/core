"""Constants for the Ollama integration."""

DOMAIN = "ollama"

CONF_MODEL = "model"
CONF_PROMPT = "prompt"

CONF_KEEP_ALIVE = "keep_alive"
DEFAULT_KEEP_ALIVE = -1  # seconds. -1 = indefinite, 0 = never

KEEP_ALIVE_FOREVER = -1
DEFAULT_TIMEOUT = 5.0  # seconds

CONF_NUM_CTX = "num_ctx"
DEFAULT_NUM_CTX = 8192
MIN_NUM_CTX = 2048
MAX_NUM_CTX = 131072

CONF_MAX_HISTORY = "max_history"
DEFAULT_MAX_HISTORY = 20

MAX_HISTORY_SECONDS = 60 * 60  # 1 hour

MODEL_NAMES = [  # https://ollama.com/library
    "alfred",
    "all-minilm",
    "aya",
    "bakllava",
    "codebooga",
    "codegeex4",
    "codegemma",
    "codellama",
    "codeqwen",
    "codestral",
    "codeup",
    "command-r",
    "command-r-plus",
    "dbrx",
    "deepseek-coder",
    "deepseek-coder-v2",
    "deepseek-llm",
    "deepseek-v2",
    "dolphincoder",
    "dolphin-llama3",
    "dolphin-mistral",
    "dolphin-mixtral",
    "dolphin-phi",
    "duckdb-nsql",
    "everythinglm",
    "falcon",
    "falcon2",
    "firefunction-v2",
    "gemma",
    "gemma2",
    "glm4",
    "goliath",
    "granite-code",
    "internlm2",
    "llama2",
    "llama2-chinese",
    "llama2-uncensored",
    "llama3",
    "llama3-chatqa",
    "llama3-gradient",
    "llama3-groq-tool-use",
    "llama-pro",
    "llava",
    "llava-llama3",
    "llava-phi3",
    "magicoder",
    "mathstral",
    "meditron",
    "medllama2",
    "megadolphin",
    "mistral",
    "mistrallite",
    "mistral-nemo",
    "mistral-openorca",
    "mixtral",
    "moondream",
    "mxbai-embed-large",
    "neural-chat",
    "nexusraven",
    "nomic-embed-text",
    "notus",
    "notux",
    "nous-hermes",
    "nous-hermes2",
    "nous-hermes2-mixtral",
    "nuextract",
    "openchat",
    "openhermes",
    "open-orca-platypus2",
    "orca2",
    "orca-mini",
    "phi",
    "phi3",
    "phind-codellama",
    "qwen",
    "qwen2",
    "samantha-mistral",
    "snowflake-arctic-embed",
    "solar",
    "sqlcoder",
    "stable-beluga",
    "stable-code",
    "stablelm2",
    "stablelm-zephyr",
    "starcoder",
    "starcoder2",
    "starling-lm",
    "tinydolphin",
    "tinyllama",
    "vicuna",
    "wizardcoder",
    "wizardlm",
    "wizardlm2",
    "wizardlm-uncensored",
    "wizard-math",
    "wizard-vicuna",
    "wizard-vicuna-uncensored",
    "xwinlm",
    "yarn-llama2",
    "yarn-mistral",
    "yi",
    "zephyr",
]
DEFAULT_MODEL = "llama3.1:latest"
