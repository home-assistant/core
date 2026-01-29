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
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEMPERATURE,
    DEFAULT,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CREDENTIALS = {
    CONF_ACCESS_KEY_ID: "test_access_key",
    CONF_SECRET_ACCESS_KEY: "test_secret_key",
    CONF_REGION: "us-east-1",
}

# Model ID that matches our mock data
TEST_MODEL_ID = "amazon.nova-pro-v1:0"

# User-input fields for conversation subentry (no llm_hass_api - auto-managed)
TEST_CONVERSATION_USER_INPUT = {
    CONF_PROMPT: "",
    CONF_CHAT_MODEL: TEST_MODEL_ID,
    CONF_MAX_TOKENS: 1024,
    CONF_TEMPERATURE: 1.0,
}

# User-input fields for AI task subentry (no llm_hass_api - auto-managed)
TEST_AI_TASK_USER_INPUT = {
    CONF_CHAT_MODEL: TEST_MODEL_ID,
    CONF_MAX_TOKENS: 1024,
    CONF_TEMPERATURE: 1.0,
}


@pytest.fixture
def mock_bedrock_client():
    """Mock boto3 bedrock client."""
    with patch("homeassistant.components.aws_bedrock.config_flow.boto3.client") as mock:
        client = MagicMock()
        client.list_foundation_models.return_value = {"modelSummaries": []}
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
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    with patch(
        "homeassistant.components.aws_bedrock.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CREDENTIALS,
        )
        await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "AWS Bedrock (us-east-1)"
    assert result2.get("data") == TEST_CREDENTIALS
    assert result2.get("options") == {}
    assert result2.get("subentries") == [
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

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    # Should use default region
    assert result2.get("data", {}).get(CONF_REGION) == DEFAULT[CONF_REGION]


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
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CREDENTIALS,
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


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

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": expected_error}


async def test_validate_credentials_permissions(
    hass: HomeAssistant,
) -> None:
    """Test that validation checks required AWS Bedrock permissions.

    According to AWS Bedrock documentation, the integration requires:
    - bedrock:ListFoundationModels - To validate credentials and list available models

    This test ensures credentials are validated by calling ListFoundationModels,
    which verifies the user has the minimum required Bedrock permissions.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aws_bedrock.config_flow.boto3.client"
    ) as mock_client:
        client_instance = MagicMock()
        # Simulate successful ListFoundationModels call
        client_instance.list_foundation_models.return_value = {
            "modelSummaries": [
                {
                    "modelId": "amazon.nova-pro-v1:0",
                    "modelName": "Nova Pro",
                    "providerName": "Amazon",
                }
            ]
        }
        mock_client.return_value = client_instance

        with patch(
            "homeassistant.components.aws_bedrock.async_setup_entry",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                TEST_CREDENTIALS,
            )

        # Verify boto3.client was called with correct service and credentials
        mock_client.assert_called_with(
            "bedrock",
            aws_access_key_id=TEST_CREDENTIALS[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=TEST_CREDENTIALS[CONF_SECRET_ACCESS_KEY],
            region_name=TEST_CREDENTIALS[CONF_REGION],
        )

        # Verify ListFoundationModels was called with TEXT modality
        # This validates the user has bedrock:ListFoundationModels permission
        client_instance.list_foundation_models.assert_called_once_with(
            byOutputModality="TEXT"
        )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == f"AWS Bedrock ({TEST_CREDENTIALS[CONF_REGION]})"


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

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert not result.get("errors")

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "My Bedrock Agent", **TEST_CONVERSATION_USER_INPUT},
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "My Bedrock Agent"
    # Data should contain llm_hass_api auto-set by the flow
    assert CONF_LLM_HASS_API in (result2.get("data") or {})


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

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert not result.get("errors")

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "My AI Task", **TEST_AI_TASK_USER_INPUT},
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "My AI Task"


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

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"


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

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    new_options = TEST_CONVERSATION_USER_INPUT.copy()
    new_options[CONF_PROMPT] = "You are a pirate assistant."
    new_options[CONF_MAX_TOKENS] = 4096

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        new_options,
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reconfigure_successful"

    # Verify the subentry was updated
    updated_subentry = next(iter(mock_config_entry.subentries.values()))
    assert updated_subentry.data[CONF_PROMPT] == "You are a pirate assistant."
    assert updated_subentry.data[CONF_MAX_TOKENS] == 4096


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

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    # AI task should not have CONF_PROMPT in schema
    data_schema = result.get("data_schema")
    assert data_schema is not None
    schema_keys = data_schema.schema.keys()
    assert CONF_NAME in [str(key) for key in schema_keys]
    assert CONF_PROMPT not in [str(key) for key in schema_keys]
