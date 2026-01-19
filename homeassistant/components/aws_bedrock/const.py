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


def supports_tool_use(model_id: str) -> bool:
    """Check if a model supports tool use.

    Based on AWS Bedrock documentation:
    https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-supported-models-features.html
    """
    # Remove region prefix if present (us., eu.)
    clean_id = model_id
    if model_id.startswith(("us.", "eu.")):
        clean_id = model_id.split(".", 1)[1]

    # Models that DO NOT support tool use (based on AWS documentation)
    # AI21 Jamba-Instruct (not Jamba 1.5)
    if clean_id.startswith("ai21.jamba-instruct"):
        return False
    # AI21 Labs Jurassic-2
    if clean_id.startswith("ai21.j2-"):
        return False
    # Amazon Titan models
    if clean_id.startswith("amazon.titan"):
        return False
    # Anthropic Claude 2.x and earlier
    if clean_id.startswith(("anthropic.claude-v2", "anthropic.claude-instant")):
        return False
    # Cohere Command (not Command R/R+)
    if clean_id.startswith(("cohere.command-text", "cohere.command-light")):
        return False
    # DeepSeek-R1
    if "deepseek-r1" in clean_id:
        return False
    # Meta Llama 2 and Llama 3 (but not 3.1, 3.2 11b/90b, or 4.x)
    if clean_id.startswith(("meta.llama2", "meta.llama3-")):
        # Check if it's Llama 3.1 or later (which support tool use)
        if not any(
            x in clean_id
            for x in (
                "llama3-1",
                "llama3-2-11b",
                "llama3-2-90b",
                "llama4",
            )
        ):
            return False
    # Meta Llama 3.2 1b and 3b (smaller versions)
    if "llama3-2-1b" in clean_id or "llama3-2-3b" in clean_id:
        return False
    # Mistral AI Instruct (non-Large/Small/Mixtral versions don't support tool use)
    # Large, Large 2, Small, and Mixtral DO support tool use
    if clean_id.startswith("mistral.mistral-"):
        # Check if it's a tool-capable Mistral variant
        if any(
            x in clean_id
            for x in (
                "large",
                "small",
                "mixtral",
            )
        ):
            return True
        # Other Mistral variants don't support tool use
        return False

    # All other models support tool use, including:
    # - AI21 Jamba 1.5 Large/Mini
    # - Amazon Nova Premier/Pro/Lite/Micro
    # - Anthropic Claude 3+
    # - Cohere Command R/R+
    # - Meta Llama 3.1, 3.2 11b/90b, 4.x
    # - Mistral Large/Small
    # - Writer Palmyra X4/X5
    return True


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
