"""Test the AWS Bedrock config flow."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import BotoCoreError, ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.aws_bedrock.config_flow import (
    DEFAULT_AI_TASK_OPTIONS,
    DEFAULT_CONVERSATION_OPTIONS,
)
from homeassistant.components.aws_bedrock.const import (
    CONF_ACCESS_KEY_ID,
    CONF_CHAT_MODEL,
    CONF_ENABLE_WEB_SEARCH,
    CONF_GOOGLE_API_KEY,
    CONF_GOOGLE_CSE_ID,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEMPERATURE,
    DEFAULT,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    LLM_API_WEB_SEARCH,
    async_get_available_models,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from tests.common import MockConfigEntry

TEST_CREDENTIALS = {
    CONF_ACCESS_KEY_ID: "test_access_key",
    CONF_SECRET_ACCESS_KEY: "test_secret_key",
    CONF_REGION: "us-east-1",
}

# Model ID that matches our mock data
TEST_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

# User-input fields for conversation subentry (no llm_hass_api - auto-managed)
TEST_CONVERSATION_USER_INPUT = {
    CONF_PROMPT: "",
    CONF_CHAT_MODEL: TEST_MODEL_ID,
    CONF_MAX_TOKENS: 1024,
    CONF_TEMPERATURE: 1.0,
    CONF_ENABLE_WEB_SEARCH: False,
    CONF_GOOGLE_API_KEY: "",
    CONF_GOOGLE_CSE_ID: "",
}

# User-input fields for AI task subentry (no llm_hass_api - auto-managed)
TEST_AI_TASK_USER_INPUT = {
    CONF_CHAT_MODEL: TEST_MODEL_ID,
    CONF_MAX_TOKENS: 1024,
    CONF_TEMPERATURE: 1.0,
    CONF_ENABLE_WEB_SEARCH: False,
    CONF_GOOGLE_API_KEY: "",
    CONF_GOOGLE_CSE_ID: "",
}


@pytest.fixture
def mock_bedrock_client():
    """Mock boto3 bedrock client."""
    with patch("homeassistant.components.aws_bedrock.config_flow.boto3.client") as mock:
        client = MagicMock()
        client.list_foundation_models.return_value = {
            "modelSummaries": [
                {
                    "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "modelName": "Claude 3 Sonnet",
                    "providerName": "Anthropic",
                }
            ]
        }
        mock.return_value = client
        yield mock


async def test_form(hass: HomeAssistant, mock_bedrock_client) -> None:
    """Test we get the form."""
    hass.config.components.add(DOMAIN)
    MockConfigEntry(
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.aws_bedrock.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CREDENTIALS,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "AWS Bedrock (us-east-1)"
    assert result2["data"] == TEST_CREDENTIALS
    assert result2["options"] == {}
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": DEFAULT_CONVERSATION_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": DEFAULT_AI_TASK_OPTIONS,
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
    ]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_default_region(
    hass: HomeAssistant, mock_bedrock_client
) -> None:
    """Test form with default region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    credentials_without_region = {
        CONF_ACCESS_KEY_ID: "test_access_key",
        CONF_SECRET_ACCESS_KEY: "test_secret_key",
    }

    with patch(
        "homeassistant.components.aws_bedrock.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            credentials_without_region,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    # Should use default region
    assert result2["data"][CONF_REGION] == DEFAULT[CONF_REGION]


async def test_duplicate_entry(hass: HomeAssistant, mock_bedrock_client) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        unique_id="test_access_key_us-east-1",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_code", "expected_error"),
    [
        (
            ClientError(
                {"Error": {"Code": "InvalidSignatureException"}}, "ListFoundationModels"
            ),
            "InvalidSignatureException",
            "invalid_auth",
        ),
        (
            ClientError(
                {"Error": {"Code": "UnrecognizedClientException"}},
                "ListFoundationModels",
            ),
            "UnrecognizedClientException",
            "invalid_auth",
        ),
        (
            ClientError(
                {"Error": {"Code": "AccessDeniedException"}}, "ListFoundationModels"
            ),
            "AccessDeniedException",
            "cannot_connect",
        ),
        (BotoCoreError(), None, "cannot_connect"),
        (Exception("Unexpected error"), None, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, side_effect, error_code, expected_error
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.boto3.client"
    ) as mock_client:
        client = MagicMock()
        client.list_foundation_models.side_effect = side_effect
        mock_client.return_value = client

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CREDENTIALS,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}


async def test_creating_conversation_subentry(
    hass: HomeAssistant,
) -> None:
    """Test creating a conversation subentry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "My Bedrock Agent", **TEST_CONVERSATION_USER_INPUT},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Bedrock Agent"
    # Data should contain llm_hass_api auto-set by the flow
    assert CONF_LLM_HASS_API in result2["data"]


async def test_creating_ai_task_subentry(
    hass: HomeAssistant,
) -> None:
    """Test creating an AI task subentry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "ai_task_data"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "My AI Task", **TEST_AI_TASK_USER_INPUT},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My AI Task"


async def test_creating_subentry_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test creating a subentry when entry is not loaded."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.NOT_LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_reconfigure_conversation_subentry(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguring a conversation subentry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
        subentries_data=[
            {
                "subentry_type": "conversation",
                "data": DEFAULT_CONVERSATION_OPTIONS,
                "title": "Test Agent",
                "unique_id": None,
            }
        ],
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_options = TEST_CONVERSATION_USER_INPUT.copy()
    new_options[CONF_PROMPT] = "You are a pirate assistant."
    new_options[CONF_MAX_TOKENS] = 4096

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            new_options,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # Verify the subentry was updated
    updated_subentry = next(iter(mock_config_entry.subentries.values()))
    assert updated_subentry.data[CONF_PROMPT] == "You are a pirate assistant."
    assert updated_subentry.data[CONF_MAX_TOKENS] == 4096


async def test_subentry_with_web_search_enabled(
    hass: HomeAssistant,
) -> None:
    """Test conversation subentry with web search enabled."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    options_with_web_search = TEST_CONVERSATION_USER_INPUT.copy()
    options_with_web_search[CONF_ENABLE_WEB_SEARCH] = True
    options_with_web_search[CONF_GOOGLE_API_KEY] = "test_api_key"
    options_with_web_search[CONF_GOOGLE_CSE_ID] = "test_cse_id"

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "Web Search Agent", **options_with_web_search},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    # Verify llm_hass_api includes web search
    assert result2["data"][CONF_LLM_HASS_API] == [
        llm.LLM_API_ASSIST,
        LLM_API_WEB_SEARCH,
    ]


async def test_subentry_without_web_search(
    hass: HomeAssistant,
) -> None:
    """Test conversation subentry without web search."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    options_without_web_search = TEST_CONVERSATION_USER_INPUT.copy()
    options_without_web_search[CONF_ENABLE_WEB_SEARCH] = False

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "Basic Agent", **options_without_web_search},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    # Verify llm_hass_api only includes assist
    assert result2["data"][CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]


async def test_subentry_invalid_model_selection(
    hass: HomeAssistant,
) -> None:
    """Test subentry with invalid model selection (separator)."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            },
            {
                "id": "meta.llama-3-70b",
                "name": "Llama 3 70B",
                "provider": "Meta",
            },
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    invalid_options = TEST_CONVERSATION_USER_INPUT.copy()
    # Use separator for the second provider "Meta"
    invalid_options[CONF_CHAT_MODEL] = "separator_Meta"

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            },
            {
                "id": "meta.llama-3-70b",
                "name": "Llama 3 70B",
                "provider": "Meta",
            },
        ],
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "Test Agent", **invalid_options},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_CHAT_MODEL: "invalid_model"}


async def test_subentry_fallback_models_on_api_error(
    hass: HomeAssistant,
) -> None:
    """Test subentry uses fallback models when API fails."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        side_effect=Exception("API Error"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    # Should still show form with fallback models
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]


async def test_ai_task_subentry_no_prompt_field(
    hass: HomeAssistant,
) -> None:
    """Test AI task subentry doesn't have prompt field."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        state=config_entries.ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock runtime data
    mock_config_entry.runtime_data = MagicMock()

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.async_get_available_models",
        return_value=[
            {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
            }
        ],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "ai_task_data"),
            context={"source": config_entries.SOURCE_USER},
        )

    # AI task should not have CONF_PROMPT in schema
    schema_keys = result["data_schema"].schema.keys()
    assert CONF_NAME in [str(key) for key in schema_keys]
    assert CONF_PROMPT not in [str(key) for key in schema_keys]


async def test_model_filtering_excludes_non_tool_models(
    hass: HomeAssistant,
) -> None:
    """Test that models without tool use support are filtered out."""
    mock_bedrock_client = MagicMock()
    # Return a mix of tool-capable and non-tool-capable models
    mock_bedrock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "amazon.nova-pro-v1:0",
                "modelName": "Nova Pro",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "amazon.titan-text-premier-v1:0",
                "modelName": "Titan Text Premier",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
                "modelName": "Claude 3 Sonnet",
                "providerName": "Anthropic",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "anthropic.claude-v2",
                "modelName": "Claude 2",
                "providerName": "Anthropic",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "meta.llama3-2-90b-instruct-v1:0",
                "modelName": "Llama 3.2 90B",
                "providerName": "Meta",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "meta.llama2-70b-chat-v1",
                "modelName": "Llama 2 70B",
                "providerName": "Meta",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
        ]
    }

    with patch("boto3.client", return_value=mock_bedrock_client):
        models = await async_get_available_models(
            hass, "test_key", "test_secret", "us-east-1"
        )

    # Only tool-capable models should be returned
    model_ids = [m["id"] for m in models]

    # These should be included (support tool use)
    assert "amazon.nova-pro-v1:0" in model_ids
    assert "anthropic.claude-3-sonnet-20240229-v1:0" in model_ids
    assert "meta.llama3-2-90b-instruct-v1:0" in model_ids

    # These should be excluded (don't support tool use)
    assert "amazon.titan-text-premier-v1:0" not in model_ids
    assert "anthropic.claude-v2" not in model_ids
    assert "meta.llama2-70b-chat-v1" not in model_ids

    # Should have exactly 3 models
    assert len(models) == 3
