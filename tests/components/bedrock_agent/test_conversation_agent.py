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

from .const import CONST_ANSWERS, CONST_PROMPT, CONST_PROMPT_CONTEXT, CONST_RESPONSES

from tests.common import MockConfigEntry

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


# @pytest.fixture(params=["anthropic.claude-v2:1", "amazon.titan-text-express-v1"]) #bedrock_agent.BedrockAgent.supported_models()
@pytest.fixture(params=bedrock_agent.BedrockAgent.supported_models())
def mock_config_entry(hass: HomeAssistant, request):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        data={
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
            "model_id": request.param,
            "prompt_context": CONST_PROMPT_CONTEXT,
            # "knowledgebase_id": ""
        },
    )
    entry.add_to_hass(hass)
    return entry


def mock_bedrock_client(modelId):
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )
    stubber = Stubber(client)
    stubber.add_response("invoke_model", build_response_body(CONST_RESPONSES[modelId]))
    stubber.activate()
    return client


async def test_default_prompt(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that the default prompt works."""
    conversationInput = conversation.ConversationInput(
        CONST_PROMPT, None, None, "123", "DE"
    )
    entry = mock_config_entry
    with mock.patch(
        "boto3.client",
        mock.MagicMock(return_value=mock_bedrock_client(entry.data["model_id"])),
    ):
        agent = bedrock_agent.BedrockAgent(hass, entry)
        conversationResult = await agent.async_process(conversationInput)
        answer = conversationResult.response.speech["plain"]["speech"]
    assert answer == CONST_ANSWERS[entry.data["model_id"]]


def build_response_body(response: str):
    """Generate streaming body response from JSON string."""
    body_encoded = json.dumps(response).encode()
    body = StreamingBody(BytesIO(body_encoded), len(body_encoded))
    return {
        "body": body,
        "contentType": "application/json",
    }
