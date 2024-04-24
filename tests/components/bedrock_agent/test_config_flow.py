"""Test the Amazon Bedrock Agent config flow."""

from unittest import mock

import boto3
from botocore.stub import Stubber
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .const import CONST_LIST_KNOWLEDGEBASE_RESPONSE, CONST_LIST_MODEL_RESPONSE

from tests.common import MockConfigEntry

CONST_DOMAIN = "bedrock_agent"


@pytest.fixture
def mock_bedrock_client():
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )
    stubber = Stubber(client)
    stubber.add_response("list_foundation_models", CONST_LIST_MODEL_RESPONSE)
    stubber.activate()
    return client


@pytest.fixture
def mock_bedrock_agent_client():
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock-agent",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )
    stubber = Stubber(client)
    stubber.add_response("list_knowledge_bases", CONST_LIST_KNOWLEDGEBASE_RESPONSE)
    stubber.add_response("list_knowledge_bases", CONST_LIST_KNOWLEDGEBASE_RESPONSE)
    stubber.activate()
    return client


@pytest.fixture
def mock_bedrock_client_errors():
    """Mock bedrock client."""
    client = boto3.client(
        service_name="bedrock",
        region_name="us-west-2",
        aws_access_key_id="abc",
        aws_secret_access_key="123",
    )
    stubber = Stubber(client)
    stubber.add_client_error(
        "list_foundation_models", service_error_code="EndpointConnectionError"
    )
    stubber.add_client_error("list_foundation_models", service_error_code="Exception")
    stubber.activate()
    return client


async def test_form(
    hass: HomeAssistant, mock_bedrock_client, mock_bedrock_agent_client
) -> None:
    """Test input form."""
    hass.config.components.add(CONST_DOMAIN)
    MockConfigEntry(
        domain=CONST_DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    with mock.patch(
        "boto3.client", side_effect=[mock_bedrock_client, mock_bedrock_agent_client]
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "title": "bedrock_agent",
                "key_id": "abc",
                "key_secret": "123",
                "region": "us-west-2",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "modelconfig"
        assert (
            len(result2["data_schema"].schema["knowledgebase_id"].config["options"])
            == 2
        )


async def test_form_errors(hass: HomeAssistant, mock_bedrock_client_errors) -> None:
    """Test input form."""
    hass.config.components.add("bedrock_agent")
    MockConfigEntry(
        domain=CONST_DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    with mock.patch(
        "boto3.client",
        mock.MagicMock(return_value=mock_bedrock_client_errors),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "title": "bedrock_agent",
                "key_id": "abc",
                "key_secret": "123",
                "region": "us-somewhere",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


async def test_invalid_model_id(hass: HomeAssistant) -> None:
    """Test unsupported model id."""
    hass.config.components.add("bedrock_agent")
    MockConfigEntry(
        domain=CONST_DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "key_id": "abc",
                "key_secret": "123",
                "region": "us-west-2",
                "model_id": "123",
                "prompt_context": "123abc",
            },
        )


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry, mock_bedrock_agent_client
) -> None:
    """Testing Options Flow."""

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with mock.patch(
        "boto3.client", mock.MagicMock(return_value=mock_bedrock_agent_client)
    ):
        options_flow = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        options = await hass.config_entries.options.async_configure(
            options_flow["flow_id"],
            {
                "model_id": "anthropic.claude-v2",
                "prompt_context": "test",
                "knowledgebase_id": "123",
            },
        )
        assert options["type"] == FlowResultType.CREATE_ENTRY
        assert options["result"]


async def test_options_flow_invalid_model_id(
    hass: HomeAssistant, mock_config_entry, mock_bedrock_agent_client
) -> None:
    """Testing Options Flow."""

    with mock.patch(
        "boto3.client", mock.MagicMock(return_value=mock_bedrock_agent_client)
    ):
        options_flow = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                options_flow["flow_id"],
                {
                    "model_id": "123",
                    "prompt_context": "test",
                    "knowledgebase_id": "123",
                },
            )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, request):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        title="bedrock_agent",
        data={
            "title": "bedrock_agent",
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
        },
        options={
            "model_id": "anthropic.claude-v2",
            "prompt_context": "test",
            "knowledgebase_id": "123",
        },
    )
    entry.add_to_hass(hass)
    return entry
