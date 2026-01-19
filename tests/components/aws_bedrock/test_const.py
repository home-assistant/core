"""Test AWS Bedrock const functions."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
import pytest

from homeassistant.components.aws_bedrock.const import (
    FALLBACK_MODELS,
    async_get_available_models,
    get_model_name,
    supports_tool_use,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        # Models that support tool use
        ("amazon.nova-pro-v1:0", True),
        ("amazon.nova-lite-v1:0", True),
        ("amazon.nova-micro-v1:0", True),
        ("amazon.nova-premier-v1:0", True),
        ("anthropic.claude-3-sonnet-20240229-v1:0", True),
        ("anthropic.claude-3-5-sonnet-20240620-v1:0", True),
        ("anthropic.claude-3-5-haiku-20241022-v1:0", True),
        ("us.anthropic.claude-3-5-sonnet-20241022-v2:0", True),
        ("eu.anthropic.claude-3-5-sonnet-20241022-v2:0", True),
        ("ai21.jamba-1-5-large-v1:0", True),
        ("ai21.jamba-1-5-mini-v1:0", True),
        ("cohere.command-r-v1:0", True),
        ("cohere.command-r-plus-v1:0", True),
        ("meta.llama3-1-8b-instruct-v1:0", True),
        ("meta.llama3-1-70b-instruct-v1:0", True),
        ("meta.llama3-2-11b-instruct-v1:0", True),
        ("meta.llama3-2-90b-instruct-v1:0", True),
        ("meta.llama4-scout-17b-v1:0", True),
        ("mistral.mistral-large-2402-v1:0", True),
        ("mistral.mistral-large-2407-v1:0", True),
        ("mistral.mistral-small-2402-v1:0", True),
        ("mistral.mixtral-8x7b-instruct-v0:1", True),
        # Models that DO NOT support tool use
        ("amazon.titan-text-premier-v1:0", False),
        ("amazon.titan-text-express-v1", False),
        ("amazon.titan-text-lite-v1", False),
        ("ai21.j2-ultra-v1", False),
        ("ai21.j2-mid-v1", False),
        ("ai21.jamba-instruct-v1:0", False),
        ("anthropic.claude-v2", False),
        ("anthropic.claude-v2:1", False),
        ("anthropic.claude-instant-v1", False),
        ("cohere.command-text-v14", False),
        ("cohere.command-light-text-v14", False),
        ("deepseek-r1", False),
        ("meta.llama2-13b-chat-v1", False),
        ("meta.llama2-70b-chat-v1", False),
        ("meta.llama3-8b-instruct-v1:0", False),
        ("meta.llama3-70b-instruct-v1:0", False),
        ("meta.llama3-2-1b-instruct-v1:0", False),
        ("meta.llama3-2-3b-instruct-v1:0", False),
        ("mistral.mistral-7b-instruct-v0:2", False),
    ],
)
def test_supports_tool_use(model_id: str, expected: bool) -> None:
    """Test that supports_tool_use correctly identifies tool-capable models."""
    assert supports_tool_use(model_id) == expected


def test_supports_tool_use_handles_region_prefix() -> None:
    """Test that region prefixes are correctly stripped before checking."""
    # Same model with and without region prefix should have same result
    assert supports_tool_use("anthropic.claude-3-sonnet-20240229-v1:0") is True
    assert supports_tool_use("us.anthropic.claude-3-sonnet-20240229-v1:0") is True
    assert supports_tool_use("eu.anthropic.claude-3-sonnet-20240229-v1:0") is True

    # Model that doesn't support tool use, with and without prefix
    assert supports_tool_use("amazon.titan-text-premier-v1:0") is False
    assert supports_tool_use("us.amazon.titan-text-premier-v1:0") is False
    assert supports_tool_use("eu.amazon.titan-text-premier-v1:0") is False


def test_get_model_name_with_inference_profile_id() -> None:
    """Test get_model_name handles inference profile IDs with region prefix."""
    # Inference profile ID with region prefix (us.vendor.model-name:version)
    result = get_model_name("us.anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert "Anthropic" in result
    assert "Claude" in result

    # EU region prefix
    result = get_model_name("eu.anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert "Anthropic" in result

    # Direct model ID without region prefix
    result = get_model_name("anthropic.claude-3-sonnet-20240229-v1:0")
    assert "Anthropic" in result
    assert "Claude" in result

    # Model ID without dots returns as-is
    result = get_model_name("simple-model")
    assert result == "simple-model"


async def test_async_get_available_models_eu_region(hass: HomeAssistant) -> None:
    """Test that EU region uses eu. prefix for inference profile models."""
    mock_bedrock_client = MagicMock()
    mock_bedrock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "modelName": "Claude 3.5 Sonnet v2",
                "providerName": "Anthropic",
                "inferenceTypesSupported": [
                    "INFERENCE_PROFILE"
                ],  # Only supports profile
            },
        ]
    }

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass,
            "test_key",
            "test_secret",
            "eu-west-1",  # EU region
        )

    # Model ID should have eu. prefix since it only supports INFERENCE_PROFILE
    assert len(models) == 1
    assert models[0]["id"].startswith("eu.")


async def test_async_get_available_models_inference_profile_only(
    hass: HomeAssistant,
) -> None:
    """Test models that only support INFERENCE_PROFILE get proper prefix."""
    mock_bedrock_client = MagicMock()
    mock_bedrock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "modelName": "Claude 3.5 Sonnet v2",
                "providerName": "Anthropic",
                "inferenceTypesSupported": ["INFERENCE_PROFILE"],  # Only profile
            },
            {
                "modelId": "amazon.nova-pro-v1:0",
                "modelName": "Nova Pro",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],  # Only on-demand
            },
        ]
    }

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass, "test_key", "test_secret", "us-east-1"
        )

    model_ids = {m["id"] for m in models}

    # INFERENCE_PROFILE only model should get us. prefix
    assert "us.anthropic.claude-3-5-sonnet-20241022-v2:0" in model_ids
    # ON_DEMAND model should use direct ID
    assert "amazon.nova-pro-v1:0" in model_ids


async def test_async_get_available_models_skips_unsupported_inference(
    hass: HomeAssistant,
) -> None:
    """Test models without ON_DEMAND or INFERENCE_PROFILE are skipped."""
    mock_bedrock_client = MagicMock()
    mock_bedrock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "amazon.nova-pro-v1:0",
                "modelName": "Nova Pro",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "some.unknown-model:v1",
                "modelName": "Unknown Model",
                "providerName": "Unknown",
                "inferenceTypesSupported": ["PROVISIONED_THROUGHPUT"],  # Not supported
            },
        ]
    }

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass, "test_key", "test_secret", "us-east-1"
        )

    # Only Nova Pro should be included (supports ON_DEMAND and tool use)
    assert len(models) == 1
    assert models[0]["id"] == "amazon.nova-pro-v1:0"


async def test_async_get_available_models_skips_duplicate_ids(
    hass: HomeAssistant,
) -> None:
    """Test duplicate model IDs are skipped."""
    mock_bedrock_client = MagicMock()
    mock_bedrock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "amazon.nova-pro-v1:0",
                "modelName": "Nova Pro",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "amazon.nova-pro-v1:0",  # Duplicate
                "modelName": "Nova Pro Duplicate",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
        ]
    }

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass, "test_key", "test_secret", "us-east-1"
        )

    # Only one entry for the model
    assert len(models) == 1


async def test_async_get_available_models_api_error_returns_fallback(
    hass: HomeAssistant,
) -> None:
    """Test API errors return fallback models."""
    mock_bedrock_client = MagicMock()
    mock_bedrock_client.list_foundation_models.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "ListFoundationModels",
    )

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass, "test_key", "test_secret", "us-east-1"
        )

    # Should return fallback models
    assert len(models) == len(FALLBACK_MODELS)
    assert all(m["provider"] == "Fallback" for m in models)
