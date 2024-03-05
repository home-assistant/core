"""Constants for the Amazon Bedrock Agent integration."""
from typing import Final

DOMAIN: Final = "bedrock_agent"

CONST_KEY_ID: Final = "key_id"
CONST_KEY_SECRET: Final = "key_secret"
CONST_REGION: Final = "region"
CONST_MODEL_ID: Final = "model_id"

CONST_MODEL_LIST: Final = [
    "amazon.titan-text-express-v1",
    "amazon.titan-text-lite-v1",
    "anthropic.claude-v2",
    "anthropic.claude-v2:1",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-instant-v1",
    "ai21.j2-mid-v1",
    "ai21.j2-ultra-v1",
    "mistral.mistral-7b-instruct-v0:2",
    "mistral.mixtral-8x7b-instruct-v0:1",
]
