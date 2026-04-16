"""Constants for the Cloudflare Workers AI integration."""

DOMAIN = "cloudflare_ai"

# Config keys
CONF_ACCOUNT_ID = "account_id"
CONF_API_TOKEN = "api_token"
CONF_USE_AI_GATEWAY = "use_ai_gateway"
CONF_GATEWAY_ID = "gateway_id"
CONF_GATEWAY_API_TOKEN = "gateway_api_token"
CONF_CHAT_MODEL = "chat_model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_PROMPT = "prompt"
CONF_ENABLE_THINKING = "enable_thinking"

# API URLs
CF_AI_GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1"

# Defaults
DEFAULT_CHAT_MODEL = "@cf/moonshotai/kimi-k2.5"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.6
DEFAULT_ENABLE_THINKING = False
DEFAULT_PROMPT = """You are a helpful voice assistant for Home Assistant.
Answer in plain text. Be brief and concise."""

# Tool calling
MAX_TOOL_ITERATIONS = 10
MAX_TOOL_ITERATIONS_EXCEEDED_MSG = (
    "Sorry, I could not complete the request after multiple attempts."
)

# Subentry types
SUBENTRY_CONVERSATION = "conversation"

# Known models by task type
CHAT_MODELS = [
    "@cf/moonshotai/kimi-k2.5",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/meta/llama-4-scout-17b-16e-instruct",
    "@cf/openai/gpt-oss-120b",
    "@cf/openai/gpt-oss-20b",
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/qwen/qwq-32b",
    "@cf/mistralai/mistral-small-3.1-24b-instruct",
    "@cf/google/gemma-3-12b-it",
    "@cf/nvidia/nemotron-3-120b-a12b",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/deepseek/deepseek-r1-distill-qwen-32b",
]

# Models known to support function calling
FUNCTION_CALLING_MODELS = [
    "@cf/moonshotai/kimi-k2.5",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/meta/llama-4-scout-17b-16e-instruct",
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/mistralai/mistral-small-3.1-24b-instruct",
    "@cf/openai/gpt-oss-120b",
    "@cf/openai/gpt-oss-20b",
    "@cf/nvidia/nemotron-3-120b-a12b",
    "@cf/zai-org/glm-4.7-flash",
]
