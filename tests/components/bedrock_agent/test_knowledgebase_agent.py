"""Tests for Bedrock Knowledgebase Features."""

from unittest import mock

import boto3
from botocore.stub import Stubber
import pytest

from homeassistant.components import bedrock_agent, conversation
from homeassistant.core import HomeAssistant

from .const import CONST_KNOWLEDGEBASE_RESPONSE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, request):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        data={
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
        },
        options={
            "model_id": "anthropic.claude-v2:1",
            "prompt_context": "",
            "knowledgebase_id": "123",
        },
    )
    entry.add_to_hass(hass)
    return entry


def mock_bedrock_client(modelId):
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock-agent-runtime",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )
    stubber = Stubber(client)
    stubber.add_response("retrieve_and_generate", CONST_KNOWLEDGEBASE_RESPONSE)
    stubber.activate()
    return client


async def test_knowledgebase(hass: HomeAssistant, mock_config_entry) -> None:
    """Testing call with Knowledge Base."""
    conversationInput = conversation.ConversationInput("test", None, None, "123", "DE")
    entry = mock_config_entry
    with mock.patch(
        "boto3.client",
        mock.MagicMock(return_value=mock_bedrock_client(entry.options["model_id"])),
    ):
        agent = bedrock_agent.BedrockAgent(hass, entry)
        conversationResult = await agent.async_process(conversationInput)
        answer = conversationResult.response.speech["plain"]["speech"]
    assert answer == "Sorry, I am unable to assist you with this request."
