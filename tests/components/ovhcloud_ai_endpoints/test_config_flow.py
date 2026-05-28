"""Test the OVHcloud AI Endpoints config flow."""

from unittest.mock import AsyncMock

import httpx
from openai import AuthenticationError, OpenAIError
import pytest

from homeassistant.components.ovhcloud_ai_endpoints.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_openai_client: AsyncMock) -> None:
    """Test the full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bla"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OVHcloud AI Endpoints"
    assert result["data"] == {CONF_API_KEY: "bla"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_account(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second account with a different API key can be added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "different_key"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OVHcloud AI Endpoints"
    assert result["data"] == {CONF_API_KEY: "different_key"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            AuthenticationError(
                message="invalid key",
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="POST", url="https://example.com"),
                ),
                body=None,
            ),
            "invalid_auth",
        ),
        (OpenAIError("boom"), "cannot_connect"),
        (Exception("boom"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors raised while validating the API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_openai_client.chat.completions.create.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_openai_client.chat.completions.create.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting the flow if an entry with the same API key already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_conversation_agent(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent subentry."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "init"

    assert result["data_schema"].schema["model"].config["options"] == [
        {
            "value": "Meta-Llama-3_3-70B-Instruct",
            "label": "Meta-Llama-3_3-70B-Instruct",
        },
        {"value": "Mistral-Nemo-Instruct-2407", "label": "Mistral-Nemo-Instruct-2407"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "Meta-Llama-3_3-70B-Instruct",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: ["assist"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Meta-Llama-3_3-70B-Instruct"
    assert result["data"] == {
        CONF_MODEL: "Meta-Llama-3_3-70B-Instruct",
        CONF_PROMPT: "you are an assistant",
        CONF_LLM_HASS_API: ["assist"],
    }


async def test_create_conversation_agent_no_control(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent without LLM API control."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "Mistral-Nemo-Instruct-2407",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "Mistral-Nemo-Instruct-2407",
        CONF_PROMPT: "you are an assistant",
    }


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (OpenAIError("boom"), "cannot_connect"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_subentry_exceptions(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test the subentry flow aborts when the API call fails."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.models.list.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_subentry_entry_not_loaded(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the subentry flow aborts when the parent entry is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow updates the API key."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_key"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            AuthenticationError(
                message="invalid key",
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="POST", url="https://example.com"),
                ),
                body=None,
            ),
            "invalid_auth",
        ),
        (OpenAIError("boom"), "cannot_connect"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test errors during reauth and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_openai_client.chat.completions.create.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_key"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_openai_client.chat.completions.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_key"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_key"
