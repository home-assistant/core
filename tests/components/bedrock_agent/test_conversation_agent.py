"""Tests for the Amazon Bedrock integration."""

from io import BytesIO
import json
import logging
from unittest import mock

import boto3
from boto3 import client
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from homeassistant.components import bedrock_agent, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONST_ANSWER, CONST_PROMPT, CONST_PROMPT_CONTEXT

from tests.common import MockConfigEntry

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CONFIG = {
    "domain": "bedrock_agent",
    "data": {
        "title": "Bedrock",
        "region": "us-west-2",
        "key_id": "abc",
        "key_secret": "123",
    },
    "options": {
        "model_id": "amazon.titan-text-express-v1",
        "prompt_context": CONST_PROMPT_CONTEXT,
        "knowledgebase_id": "",
    },
}


# @pytest.fixture(params=bedrock_agent.BedrockAgent.supported_models())
@pytest.fixture
def mock_config_entry(hass: HomeAssistant, request: pytest.FixtureRequest):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        data={
            "title": "Bedrock",
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
        },
        options={
            "model_id": "amazon.titan-text-express-v1",
            "prompt_context": CONST_PROMPT_CONTEXT,
            "knowledgebase_id": "",
        },
    )
    entry.add_to_hass(hass)
    return entry


def init_bedrock_client() -> client:
    """Initiate bedrock client."""
    return boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )


def mock_bedrock_client(answer: str):
    """Mock bedrock client."""
    client = init_bedrock_client()
    stubber = Stubber(client)
    stubber.add_response("converse", build_response(answer))
    stubber.activate()
    return client


def mock_bedrock_client_error(answer: str):
    """Mock bedrock client."""
    client = init_bedrock_client()
    stubber = Stubber(client)
    stubber.add_client_error(
        "converse",
        service_message="You don't have access to the model with the specified model ID.",
    )
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
        mock.MagicMock(return_value=mock_bedrock_client(CONST_ANSWER)),
    ):
        agent = bedrock_agent.BedrockAgent(hass, entry)
        conversationResult = await agent.async_process(conversationInput)
        answer = conversationResult.response.speech["plain"]["speech"]
    assert answer == CONST_ANSWER


async def test_cognitive_service(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that the default prompt works."""

    entry = mock_config_entry
    await hass.config_entries.async_setup(entry.entry_id)

    data = {"prompt": "Hello there."}

    with mock.patch(
        "boto3.client",
        mock.MagicMock(return_value=mock_bedrock_client(CONST_ANSWER)),
    ):
        result = await hass.services.async_call(
            domain="bedrock_agent",
            service="cognitive_task",
            service_data=data,
            return_response=True,
            blocking=True,
        )

    assert result == {"text": CONST_ANSWER}


async def test_missing_model_access(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that the default prompt works."""

    entry = mock_config_entry
    await hass.config_entries.async_setup(entry.entry_id)

    data = {"prompt": "Hello there."}

    with mock.patch(
        "boto3.client",
        mock.MagicMock(return_value=mock_bedrock_client_error(CONST_ANSWER)),
    ):
        try:
            result = await hass.services.async_call(
                domain="bedrock_agent",
                service="cognitive_task",
                service_data=data,
                return_response=True,
                blocking=True,
            )
        except HomeAssistantError as error:
            result = error

    assert (
        result.args[0]
        == "Bedrock Error: `You don't have access to the model with the specified model ID.`"
    )


async def test_image_type(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that the default prompt works."""

    entry = mock_config_entry
    await hass.config_entries.async_setup(entry.entry_id)

    data_url = {"prompt": "Hello there.", "image_urls": ["http://localhost/image.mp3"]}

    data_file = {"prompt": "Hello there.", "image_filenames": ["/image.mp3"]}

    with (
        mock.patch(
            "boto3.client",
            mock.MagicMock(return_value=mock_bedrock_client_error(CONST_ANSWER)),
        ),
        mock.patch(
            "homeassistant.core.Config.is_allowed_path",
            mock.MagicMock(return_value=True),
        ),
        mock.patch("pathlib.Path.exists", mock.MagicMock(return_value=True)),
    ):
        try:
            result = await hass.services.async_call(
                domain="bedrock_agent",
                service="cognitive_task",
                service_data=data_url,
                return_response=True,
                blocking=True,
            )
        except HomeAssistantError as error:
            result = error

        try:
            result2 = await hass.services.async_call(
                domain="bedrock_agent",
                service="cognitive_task",
                service_data=data_file,
                return_response=True,
                blocking=True,
            )
        except HomeAssistantError as error:
            result2 = error

    assert result.args[0] == "`http://localhost/image.mp3` is not an image"
    assert result2.args[0] == "`/image.mp3` is not an image"


async def test_file_not_exist(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that the default prompt works."""

    entry = mock_config_entry
    await hass.config_entries.async_setup(entry.entry_id)

    data_file = {"prompt": "Hello there.", "image_filenames": ["/image.mp3"]}

    with (
        mock.patch(
            "boto3.client",
            mock.MagicMock(return_value=mock_bedrock_client_error(CONST_ANSWER)),
        ),
        mock.patch(
            "homeassistant.core.Config.is_allowed_path",
            mock.MagicMock(return_value=True),
        ),
        mock.patch("pathlib.Path.exists", mock.MagicMock(return_value=False)),
    ):
        try:
            result2 = await hass.services.async_call(
                domain="bedrock_agent",
                service="cognitive_task",
                service_data=data_file,
                return_response=True,
                blocking=True,
            )
        except HomeAssistantError as error:
            result2 = error

    assert result2.args[0] == "`/image.mp3` does not exist"


def build_response_body(response: str):
    """Generate streaming body response from JSON string."""
    body_encoded = json.dumps(response).encode()
    body = StreamingBody(BytesIO(body_encoded), len(body_encoded))
    return {
        "body": body,
        "contentType": "application/json",
    }


def build_response(answer: str) -> dict:
    """Generate a response."""
    return {
        "ResponseMetadata": {
            "RequestId": "474ef87b-6736-4cdc-ba44-1d1cd3172006",
            "HTTPStatusCode": 200,
            "HTTPHeaders": {
                "date": "Sat, 08 Jun 2024 04:55:18 GMT",
                "content-type": "application/json",
                "content-length": "206",
                "connection": "keep-alive",
                "x-amzn-requestid": "474ef87b-6736-4cdc-ba44-1d1cd3172006",
            },
            "RetryAttempts": 0,
        },
        "output": {"message": {"role": "assistant", "content": [{"text": answer}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 8, "outputTokens": 6, "totalTokens": 14},
        "metrics": {"latencyMs": 354},
    }
