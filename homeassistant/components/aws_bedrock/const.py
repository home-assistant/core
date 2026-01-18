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

DEFAULT = {
    CONF_CHAT_MODEL: "us.amazon.nova-pro-v1:0",
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 1.0,
    CONF_REGION: "us-east-1",
    CONF_ENABLE_WEB_SEARCH: False,
}

# Fallback models if API call fails - Nova models first
FALLBACK_MODELS = [
    "us.amazon.nova-pro-v1:0",
    "us.amazon.nova-lite-v1:0",
    "us.amazon.nova-premier-v1:0",
    "us.meta.llama3-3-70b-instruct-v1:0",
]


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

            for model in response.get("modelSummaries", []):
                model_id = model.get("modelId")
                if not model_id or model_id in seen_ids:
                    continue

                # Only include models that support the Converse API
                # Check if model supports CONVERSE inference type
                inference_types = model.get("inferenceTypesSupported", [])
                if "ON_DEMAND" not in inference_types:
                    continue

                seen_ids.add(model_id)

                # Try to get cross-region inference profile ID if available
                # Inference profiles are preferred for on-demand access
                display_id = model_id
                if model.get("modelArn"):
                    # Check if this is available via inference profile
                    provider_name = model.get("providerName", "").lower()
                    if provider_name and not model_id.startswith(("us.", "eu.")):
                        # Try inference profile format
                        inference_id = f"us.{model_id}"
                        display_id = inference_id

                models.append(
                    {
                        "id": display_id,
                        "name": get_model_name(display_id),
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
