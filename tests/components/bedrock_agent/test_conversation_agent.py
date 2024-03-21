"""Tests for the Amazon Bedrock integration."""
from io import BytesIO
import json
import logging
from unittest import mock

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from homeassistant.components import bedrock_agent, conversation
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        data={
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
            "model_id": "anthropic.claude-v2:1",
            "prompt_context": "Prompt Context",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_bedrock_client():
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name="Region",
        aws_access_key_id="Key ID",
        aws_secret_access_key="Key Secret",
    )
    stubber = Stubber(client)

    body_encoded = json.dumps(
        {
            "completion": "General Kenobi.",
            "stop_reason": "stop_sequence",
            "stop": "\n\nHuman:",
        }
    ).encode()

    body = StreamingBody(BytesIO(body_encoded), len(body_encoded))

    expected_response = {
        "body": body,
        "contentType": "application/json",
    }

    stubber.add_response("invoke_model", expected_response)
    stubber.activate()
    return client


async def test_default_prompt(
    hass: HomeAssistant, mock_config_entry, mock_bedrock_client
) -> None:
    """Test that the default prompt works."""
    conversationInput = conversation.ConversationInput("hello", None, None, "123", "DE")
    entry = mock_config_entry
    with mock.patch("boto3.client", mock.MagicMock(return_value=mock_bedrock_client)):
        agent = bedrock_agent.BedrockAgent(hass, entry)
        conversationResult = await agent.async_process(conversationInput)
        answer = conversationResult.response.speech["plain"]["speech"]
    assert answer == "General Kenobi."
