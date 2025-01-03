"""Constants for the Amazon Bedrock Agent integration."""

from typing import Final

DOMAIN: Final = "bedrock_agent"

CONST_KEY_ID: Final = "key_id"
CONST_KEY_SECRET: Final = "key_secret"
CONST_REGION: Final = "region"
CONST_MODEL_ID: Final = "model_id"
CONST_KNOWLEDGEBASE_ID: Final = "knowledgebase_id"
CONST_AGENT_ID: Final = "agent_id"
CONST_AGENT_ALIAS_ID: Final = "agent_alias_id"
CONST_TITLE: Final = "title"

CONST_PROMPT_CONTEXT: Final = "prompt_context"
CONST_MODEL_LIST: Final = [
    "amazon.titan-text-express-v1",
    "amazon.titan-text-lite-v1",
    "anthropic.claude-v2",
    "anthropic.claude-v2:1",
    "anthropic.claude-instant-v1",
    "ai21.j2-mid-v1",
    "ai21.j2-ultra-v1",
    "cohere.command-text-v14",
    "cohere.command-light-text-v14",
    "cohere.command-r-v1:0",
    "cohere.command-r-plus-v1:0",
    "meta.llama2-13b-chat-v1",
    "meta.llama2-70b-chat-v1",
    "meta.llama3-8b-instruct-v1:0",
    "meta.llama3-70b-instruct-v1:0",
    "mistral.mistral-7b-instruct-v0:2",
    "mistral.mixtral-8x7b-instruct-v0:1",
    "mistral.mistral-large-2402-v1:0",
    "mistral.mistral-small-2402-v1:0",
]

CONST_SERVICE_PARAM_PROMPT: Final = "prompt"
CONST_SERVICE_PARAM_MODEL_ID: Final = "model_id"
CONST_SERVICE_PARAM_IMAGE_URLS: Final = "image_urls"
CONST_SERVICE_PARAM_FILENAMES: Final = "image_filenames"
