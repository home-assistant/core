"""Test the Amazon Bedrock Agent config flow."""

import boto3
from botocore.stub import Stubber
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .const import CONST_LIST_MODEL_RESPONSE

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


# async def test_form(hass: HomeAssistant, mock_bedrock_client) -> None:
#     """Test input form."""
#     hass.config.components.add(CONST_DOMAIN)
#     MockConfigEntry(
#         domain=CONST_DOMAIN,
#         state=config_entries.ConfigEntryState.LOADED,
#     ).add_to_hass(hass)

#     result = await hass.config_entries.flow.async_init(
#         CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     assert result["type"] == FlowResultType.FORM

#     with mock.patch(
#         "boto3.client",
#         mock.MagicMock(return_value=mock_bedrock_client),
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={
#                 "key_id": "abc",
#                 "key_secret": "123",
#                 "region": "us-west-2",
#                 #"model_id": "ai21.j2-mid-v1",
#                 #"prompt_context": "123abc",
#             },
#         )

#     assert result2["type"] == FlowResultType.CREATE_ENTRY
#     assert result2["title"] == "bedrock_agent"


# async def test_form_errors(hass: HomeAssistant, mock_bedrock_client_errors) -> None:
#     """Test input form."""
#     hass.config.components.add("bedrock_agent")
#     MockConfigEntry(
#         domain=CONST_DOMAIN,
#         state=config_entries.ConfigEntryState.LOADED,
#     ).add_to_hass(hass)

#     result = await hass.config_entries.flow.async_init(
#         CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     assert result["type"] == FlowResultType.FORM

#     with mock.patch(
#         "boto3.client",
#         mock.MagicMock(return_value=mock_bedrock_client_errors),
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             user_input={
#                 "key_id": "abc",
#                 "key_secret": "123",
#                 "region": "us-somewhere",
#                 "model_id": "ai21.j2-mid-v1",
#                 "prompt_context": "123abc",
#             },
#         )

#     assert result2["type"] == FlowResultType.FORM
#     assert result2["errors"]["base"] == "invalid_auth"


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


# async def test_options_flow(hass: HomeAssistant, mock_config_entry) -> None:
#     """Testing Options Flow."""
#     options_flow = await hass.config_entries.options.async_init(
#         mock_config_entry.entry_id
#     )
#     options = await hass.config_entries.options.async_configure(
#         options_flow["flow_id"],
#         {
#             "key_id": "abc",
#             "key_secret": "123",
#             "region": "us-west-2",
#             "model_id": "anthropic.claude-v2",
#             "prompt_context": "123abc",
#         },
#     )
#     assert options["type"] == FlowResultType.FORM


# async def test_options_flow_invalid_model_id(
#     hass: HomeAssistant, mock_config_entry
# ) -> None:
#     """Testing Options Flow."""
#     options_flow = await hass.config_entries.options.async_init(
#         mock_config_entry.entry_id
#     )

#     with pytest.raises(InvalidData):
#         await hass.config_entries.options.async_configure(
#             options_flow["flow_id"],
#             {
#                 "key_id": "abc",
#                 "key_secret": "123",
#                 "region": "us-west-2",
#                 "model_id": "123",
#                 "prompt_context": "123abc",
#             },
#         )


# @pytest.fixture
# def mock_config_entry(hass: HomeAssistant, request):
#     """Mock a config entry."""
#     entry = MockConfigEntry(
#         domain="bedrock_agent",
#         data={
#             "region": "us-west-2",
#             "key_id": "abc",
#             "key_secret": "123",
#             "model_id": "anthropic.claude-v2",
#             "prompt_context": "test",
#         },
#     )
#     entry.add_to_hass(hass)
#     return entry
