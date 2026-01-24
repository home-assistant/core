"""Constants for the AWS Bedrock integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_REGION

DOMAIN = "aws_bedrock"
LOGGER = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "AWS Bedrock conversation"
DEFAULT_AI_TASK_NAME = "AWS Bedrock AI Task"

CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"

DEFAULT = {
    CONF_CHAT_MODEL: "amazon.nova-pro-v1:0",
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 1.0,
    CONF_REGION: "us-east-1",
}

# Max number of tool iterations
MAX_TOOL_ITERATIONS = 10

# Available AWS Nova models
AVAILABLE_MODELS = [
    {
        "id": "amazon.nova-pro-v1:0",
        "name": "Amazon Nova Pro",
    },
    {
        "id": "amazon.nova-lite-v1:0",
        "name": "Amazon Nova Lite",
    },
    {
        "id": "amazon.nova-micro-v1:0",
        "name": "Amazon Nova Micro",
    },
]


# Available AWS regions with Bedrock
AVAILABLE_REGIONS = [
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-southeast-1",
    "ap-northeast-1",
]
