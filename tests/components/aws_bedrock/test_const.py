"""Test AWS Bedrock const functions."""

import pytest

from homeassistant.components.aws_bedrock.const import supports_tool_use


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
