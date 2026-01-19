"""Constants for the AWS Bedrock integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DOMAIN = "aws_bedrock"
LOGGER = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "AWS Bedrock conversation"
DEFAULT_AI_TASK_NAME = "AWS Bedrock AI Task"

CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"
CONF_REGION = "region"
CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_ENABLE_WEB_SEARCH = "enable_web_search"
CONF_GOOGLE_API_KEY = "google_api_key"
CONF_GOOGLE_CSE_ID = "google_cse_id"

LLM_API_WEB_SEARCH = "aws_bedrock_web_search"

DEFAULT = {
    CONF_CHAT_MODEL: "amazon.nova-pro-v1:0",
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 1.0,
    CONF_REGION: "us-east-1",
    CONF_ENABLE_WEB_SEARCH: False,
}

# Fallback models if API call fails - only includes models that support tool use
# Models that only support INFERENCE_PROFILE need the us./eu. prefix
FALLBACK_MODELS = [
    "amazon.nova-pro-v1:0",  # Supports ON_DEMAND and tool use
    "amazon.nova-lite-v1:0",  # Supports ON_DEMAND and tool use
    "amazon.nova-micro-v1:0",  # Supports ON_DEMAND and tool use
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0",  # INFERENCE_PROFILE only, supports tool use
]

# Max number of tool iterations
MAX_TOOL_ITERATIONS = 10

# Model ID prefixes that support tool use
# Based on: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-supported-models-features.html
TOOL_USE_SUPPORTED_MODEL_PREFIXES = {
    # AI21 Labs
    "ai21.jamba-1-5-large",
    "ai21.jamba-1-5-mini",
    # Amazon Nova
    "amazon.nova-premier",
    "amazon.nova-pro",
    "amazon.nova-lite",
    "amazon.nova-micro",
    # Anthropic Claude 3+
    "anthropic.claude-3-",
    "anthropic.claude-3.",
    "anthropic.claude-4",
    # Cohere Command R
    "cohere.command-r-",
    "cohere.command-r-plus",
    # Meta Llama 3.1+
    "meta.llama3-1-",
    "meta.llama3-2-11b",
    "meta.llama3-2-90b",
    "meta.llama4",
    # Mistral
    "mistral.mistral-large",
    "mistral.mistral-small",
    "mistral.mixtral",
    "mistral.pixtral-large",
    # Writer
    "writer.palmyra-x4",
    "writer.palmyra-x5",
}


def supports_tool_use(model_id: str) -> bool:
    """Check if a model supports tool use based on its ID prefix."""
    # Remove region prefix if present (us., eu.)
    clean_id = model_id.removeprefix("us.").removeprefix("eu.")
    return any(
        clean_id.startswith(prefix) for prefix in TOOL_USE_SUPPORTED_MODEL_PREFIXES
    )


def get_model_name(model_id: str) -> str:
    """Get a human-readable name for a model ID."""
    # Extract readable name from model ID
    if "." in model_id:
        parts = model_id.split(".")
        # Handle inference profile IDs (us.anthropic.claude-...)
        if len(parts) >= 3:
            vendor = parts[1]
            model_name = ".".join(parts[2:]).split(":", maxsplit=1)[0]
            return f"{vendor.title()} {model_name.replace('-', ' ').title()}"
        # Handle direct model IDs (anthropic.claude-...)
        vendor = parts[0]
        model_name = ".".join(parts[1:]).split(":", maxsplit=1)[0]
        return f"{vendor.title()} {model_name.replace('-', ' ').title()}"
    return model_id


async def async_get_available_models(
    hass: HomeAssistant, access_key: str, secret_key: str, region: str
) -> list[dict[str, str]]:
    """Get available models from AWS Bedrock."""

    def _fetch_models() -> list[dict[str, str]]:
        """Fetch models from Bedrock API."""
        try:
            bedrock_client = boto3.client(
                "bedrock",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            response = bedrock_client.list_foundation_models(
                byOutputModality="TEXT",
            )

            models = []
            seen_ids = set()

            # Determine inference profile prefix based on region
            if region.startswith("eu-"):
                profile_prefix = "eu."
            else:
                profile_prefix = "us."

            for model in response.get("modelSummaries", []):
                model_id = model.get("modelId")
                if not model_id or model_id in seen_ids:
                    continue

                # Include models that support either ON_DEMAND or INFERENCE_PROFILE
                inference_types = model.get("inferenceTypesSupported", [])
                supports_on_demand = "ON_DEMAND" in inference_types
                supports_inference_profile = "INFERENCE_PROFILE" in inference_types

                if not supports_on_demand and not supports_inference_profile:
                    continue

                # Only include models that support tool use
                if not supports_tool_use(model_id):
                    continue

                seen_ids.add(model_id)

                # Determine the correct model ID to use for the Converse API
                # Models that ONLY support INFERENCE_PROFILE must use an inference
                # profile ID (e.g., us.anthropic.claude-3-5-sonnet-20241022-v2:0)
                if supports_on_demand:
                    # Use the direct model ID for on-demand models
                    use_model_id = model_id
                else:
                    # Use inference profile ID for models that only support profiles
                    use_model_id = f"{profile_prefix}{model_id}"

                models.append(
                    {
                        "id": use_model_id,
                        "name": get_model_name(model_id),
                        "provider": model.get("providerName", "Unknown"),
                    }
                )

            # Sort by provider, then name
            models.sort(key=lambda x: (x["provider"], x["name"]))

        except (BotoCoreError, ClientError) as err:
            LOGGER.warning("Failed to fetch models from Bedrock API: %s", err)
            # Return fallback models if API call failed
            models = [
                {
                    "id": model_id,
                    "name": get_model_name(model_id),
                    "provider": "Fallback",
                }
                for model_id in FALLBACK_MODELS
            ]

        return models

    return await hass.async_add_executor_job(_fetch_models)


# Available AWS regions with Bedrock
AVAILABLE_REGIONS = [
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-southeast-1",
    "ap-northeast-1",
]
