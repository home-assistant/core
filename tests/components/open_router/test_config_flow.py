"""Test the OpenRouter config flow."""

from unittest.mock import AsyncMock

import pytest
from python_open_router import OpenRouterError

from homeassistant.components.open_router.const import CONF_PROMPT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
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
    assert result["data"] == {CONF_API_KEY: "bla"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OpenRouterError("exception"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors from the OpenRouter API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_open_router_client.get_key_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_open_router_client.get_key_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting the flow if an entry already exists."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_conversation_agent(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-3.5-turbo", "label": "OpenAI: GPT-3.5 Turbo"},
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-3.5-turbo",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: ["assist"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "openai/gpt-3.5-turbo",
        CONF_PROMPT: "you are an assistant",
        CONF_LLM_HASS_API: ["assist"],
    }


async def test_create_conversation_agent_no_control(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent without control over the LLM API."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-3.5-turbo", "label": "OpenAI: GPT-3.5 Turbo"},
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-3.5-turbo",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "openai/gpt-3.5-turbo",
        CONF_PROMPT: "you are an assistant",
    }


async def test_create_ai_task(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an AI Task."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/gpt-4"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MODEL: "openai/gpt-4"}


@pytest.mark.parametrize(
    "subentry_type",
    ["conversation", "ai_task_data"],
)
@pytest.mark.parametrize(
    ("exception", "reason"),
    [(OpenRouterError("exception"), "cannot_connect"), (Exception, "unknown")],
)
async def test_subentry_exceptions(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
    exception: Exception,
    reason: str,
) -> None:
    """Test subentry flow exceptions."""
    await setup_integration(hass, mock_config_entry)

    mock_open_router_client.get_models.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
