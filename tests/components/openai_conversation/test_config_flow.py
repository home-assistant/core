"""Test the OpenAI Conversation config flow."""

from collections.abc import Generator
from contextlib import ExitStack
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qsl, urlparse

import httpx2
from openai import APIConnectionError, AuthenticationError, BadRequestError
from openai.types.responses import Response, ResponseOutputMessage, ResponseOutputText
import pytest

from homeassistant import config_entries
from homeassistant.components.openai_conversation.chatgpt_auth import (
    CLIENT_ID_PREFIX,
    DYNAMIC_AGENT_CLIENT,
    PLAN_SCOPE,
    REDIRECT_URI,
    SUBSCRIPTION_MODEL_SUGGESTIONS,
    TOKEN_URL,
)
from homeassistant.components.openai_conversation.config_flow import (
    RECOMMENDED_CONVERSATION_OPTIONS,
    OpenAIConfigFlow,
)
from homeassistant.components.openai_conversation.const import (
    AUTH_METHOD_API_KEY,
    AUTH_METHOD_CHATGPT,
    CONF_AUTH_METHOD,
    CONF_CALLBACK_URL,
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_EXT_AGENT_HOST_ID,
    CONF_ID_TOKEN,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_PRO_MODE,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_RECOMMENDED,
    CONF_SCOPES,
    CONF_SERVICE_TIER,
    CONF_STORE_RESPONSES,
    CONF_SUB,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_TTS_SPEED,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import SelectSelector
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.openai_conversation import (
    create_chatgpt_id_token,
    create_chatgpt_jwks,
    create_chatgpt_rsa_key,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    # Pretend we already set up a config entry.
    hass.config.components.add("openai_conversation")
    MockConfigEntry(
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"
    # The method choice and the credential are separate steps: the method step
    # must not show the API key field, and the API key step must not show the
    # method.
    assert set(result["data_schema"].schema) == {CONF_AUTH_METHOD}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"
    assert set(result["data_schema"].schema) == {CONF_API_KEY}

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.openai_conversation.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bla",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "api_key": "bla",
    }
    assert result2["options"] == {}
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": RECOMMENDED_CONVERSATION_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": RECOMMENDED_AI_TASK_OPTIONS,
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "stt",
            "data": RECOMMENDED_STT_OPTIONS,
            "title": DEFAULT_STT_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "tts",
            "data": RECOMMENDED_TTS_OPTIONS,
            "title": DEFAULT_TTS_NAME,
            "unique_id": None,
        },
    ]
    assert result2["version"] == 2
    assert result2["minor_version"] == 7
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["step_id"] == "api_key"

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_creating_conversation_subentry(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "My Custom Agent", **RECOMMENDED_CONVERSATION_OPTIONS},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Custom Agent"

    processed_options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
    processed_options[CONF_PROMPT] = processed_options[CONF_PROMPT].strip()

    assert result2["data"] == processed_options


async def test_creating_conversation_subentry_not_loaded(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry when entry is not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_recommended(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the subentry flow with recommended settings."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "recommended": True,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data["prompt"] == "Speak like a pirate"


@pytest.mark.usefixtures("mock_init_component")
async def test_subentry_unsupported_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the subentry form giving error about models not supported."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    await hass.async_block_till_done()
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "o1-mini",
        },
    )
    await hass.async_block_till_done()
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["errors"] == {"chat_model": "model_not_supported"}

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-5",
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"], {}
    )
    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("model", "reasoning_effort_options"),
    [
        ("o4-mini", ["low", "medium", "high"]),
        ("gpt-5", ["minimal", "low", "medium", "high"]),
        ("gpt-5.1", ["none", "low", "medium", "high"]),
        ("gpt-5.2", ["none", "low", "medium", "high", "xhigh"]),
        ("gpt-5.2-pro", ["medium", "high", "xhigh"]),
        ("gpt-5.3-codex", ["none", "low", "medium", "high", "xhigh"]),
        ("gpt-5.4", ["none", "low", "medium", "high", "xhigh"]),
        ("gpt-5.4-pro", ["medium", "high", "xhigh"]),
        ("gpt-5.5", ["none", "low", "medium", "high", "xhigh"]),
        ("gpt-5.5-pro", ["medium", "high", "xhigh"]),
        ("gpt-5.6", ["none", "low", "medium", "high", "xhigh", "max"]),
        ("gpt-6-luna", ["none", "low", "medium", "high", "xhigh", "max"]),
        ("gpt-6-astra", ["low", "medium", "high", "xhigh", "max"]),
    ],
)
async def test_subentry_reasoning_effort_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model: str,
    reasoning_effort_options: list[str],
) -> None:
    """Test the list reasoning effort options."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: model,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"
    assert (
        subentry_flow["data_schema"].schema[CONF_REASONING_EFFORT].config["options"]
        == reasoning_effort_options
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("subentry_type", ["conversation", "ai_task_data"])
@pytest.mark.parametrize("reasoning_effort", ["none", "low"])
async def test_subentry_luna_reasoning_effort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
    reasoning_effort: str,
) -> None:
    """Test that Luna reasoning effort can be selected and saved."""
    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == subentry_type
    )
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_RECOMMENDED: False}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHAT_MODEL: "gpt-6-luna"}
    )
    assert result["step_id"] == "model"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_REASONING_EFFORT: reasoning_effort}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    saved = mock_config_entry.subentries[subentry.subentry_id].data
    assert saved[CONF_CHAT_MODEL] == "gpt-6-luna"
    assert saved[CONF_REASONING_EFFORT] == reasoning_effort


@pytest.mark.parametrize(
    ("model", "has_reasoning_summary"),
    [
        ("o3", True),
        ("o4-mini", True),
        ("gpt-5", True),
        ("gpt-5-mini", True),
        ("gpt-5-pro", True),
        ("gpt-6-astra", True),
        ("gpt-4o", False),
        ("gpt-4.1", False),
    ],
)
async def test_subentry_reasoning_summary_visibility(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model: str,
    has_reasoning_summary: bool,
) -> None:
    """Test that reasoning_summary option is shown for all reasoning models."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: model,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"
    assert (CONF_REASONING_SUMMARY in subentry_flow["data_schema"].schema) == (
        has_reasoning_summary
    )


@pytest.mark.parametrize(
    ("model", "reasoning_summary_options"),
    [
        ("o3", ["off", "auto", "detailed"]),
        ("o4-mini", ["off", "auto", "detailed"]),
        ("gpt-5", ["off", "auto", "concise", "detailed"]),
        ("gpt-5-mini", ["off", "auto", "concise", "detailed"]),
        ("gpt-6-astra", ["off", "auto", "concise", "detailed"]),
    ],
)
async def test_subentry_reasoning_summary_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model: str,
    reasoning_summary_options: list[str],
) -> None:
    """Test the list of reasoning summary options for reasoning models."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: model,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"
    assert (
        subentry_flow["data_schema"].schema[CONF_REASONING_SUMMARY].config["options"]
        == reasoning_summary_options
    )


async def test_subentry_reasoning_summary_default_sanitized_on_model_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test that a stored 'concise' default is sanitized to 'auto' for o* models."""
    subentry = next(
        s
        for s in mock_config_entry.subentries.values()
        if s.subentry_type == "conversation"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_REASONING_SUMMARY: "concise"},
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["step_id"] == "init"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["step_id"] == "additional"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {CONF_CHAT_MODEL: "o3"},
    )
    assert subentry_flow["step_id"] == "model"

    schema = subentry_flow["data_schema"].schema
    summary_key = next(k for k in schema if k == CONF_REASONING_SUMMARY)
    assert summary_key.default() == RECOMMENDED_REASONING_SUMMARY


@pytest.mark.parametrize(
    ("model", "service_tier_options"),
    [
        ("gpt-5.6", ["auto", "flex", "default", "priority"]),
        ("gpt-5.5", ["auto", "flex", "default", "priority"]),
        ("gpt-5.4", ["auto", "flex", "default", "priority"]),
        ("gpt-5.4-pro", ["auto", "flex", "default", "priority"]),
        ("gpt-5.2", ["auto", "flex", "default", "priority"]),
        ("gpt-5.1", ["auto", "flex", "default", "priority"]),
        ("gpt-5", ["auto", "flex", "default", "priority"]),
        ("gpt-5-mini", ["auto", "flex", "default", "priority"]),
        ("gpt-5-nano", ["auto", "flex", "default"]),
        ("o3", ["auto", "flex", "default", "priority"]),
        ("o4-mini", ["auto", "flex", "default", "priority"]),
        ("gpt-5.3-codex", ["auto", "default", "priority"]),
        ("gpt-5.2-codex", ["auto", "default", "priority"]),
        ("gpt-5.1-codex-max", ["auto", "default", "priority"]),
        ("gpt-5-codex", ["auto", "default", "priority"]),
        ("gpt-4.1", ["auto", "default", "priority"]),
        ("gpt-4.1-mini", ["auto", "default", "priority"]),
        ("gpt-4.1-nano", ["auto", "default", "priority"]),
        ("gpt-4o", ["auto", "default", "priority"]),
        ("gpt-4o-2024-05-13", ["auto", "default", "priority"]),
        ("gpt-4o-mini", ["auto", "default", "priority"]),
        ("gpt-5-chat-latest", []),
        ("gpt-5.2-pro", []),
        ("o3-mini", []),
    ],
)
async def test_subentry_service_tier_list(
    hass: HomeAssistant,
    mock_config_entry,
    mock_init_component,
    model,
    service_tier_options,
) -> None:
    """Test the list of service tier options."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: model,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"
    assert (
        subentry_flow["data_schema"].schema[CONF_SERVICE_TIER].config["options"]
        if subentry_flow["data_schema"].schema.get(CONF_SERVICE_TIER)
        else []
    ) == service_tier_options


@pytest.mark.parametrize(
    ("parameter", "error"),
    [
        (CONF_WEB_SEARCH, "web_search_minimal_reasoning"),
        (CONF_CODE_INTERPRETER, "code_interpreter_minimal_reasoning"),
    ],
)
async def test_subentry_unsupported_reasoning_effort(
    hass: HomeAssistant, mock_config_entry, mock_init_component, parameter, error
) -> None:
    """Test subentry form error on unsupported reasoning effort."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-5",
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"

    # Configure model step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_REASONING_EFFORT: "minimal",
            parameter: True,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["errors"] == {parameter: error}

    # Reconfigure model step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_REASONING_EFFORT: "low",
            parameter: True,
        },
    )
    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "cannot_connect"),
        (
            AuthenticationError(
                response=httpx2.Response(status_code=None, request=""),
                body=None,
                message=None,
            ),
            "invalid_auth",
        ),
        (
            BadRequestError(
                response=httpx2.Response(status_code=None, request=""),
                body=None,
                message=None,
            ),
            "unknown",
        ),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["step_id"] == "api_key"

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bla",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.openai_conversation.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bla",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("current_options", "new_options", "expected_options"),
    [
        (  # Test clearing every llm api is stored as an empty list
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
                CONF_PROMPT: "",
            },
            (
                {
                    CONF_RECOMMENDED: True,
                    CONF_LLM_HASS_API: [],
                    CONF_PROMPT: "",
                },
            ),
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: [],
                CONF_PROMPT: "",
            },
        ),
        (  # Test converting single llm api format to list
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: "assist",
                CONF_PROMPT: "",
            },
            (
                {
                    CONF_RECOMMENDED: True,
                    CONF_LLM_HASS_API: ["assist"],
                    CONF_PROMPT: "",
                },
            ),
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
                CONF_PROMPT: "",
            },
        ),
        (  # options for reasoning models
            {},
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pro",
                },
                {
                    CONF_TEMPERATURE: 1.0,
                    CONF_CHAT_MODEL: "o1-pro",
                    CONF_TOP_P: RECOMMENDED_TOP_P,
                    CONF_MAX_TOKENS: 10000,
                },
                {
                    CONF_REASONING_EFFORT: "high",
                    CONF_CODE_INTERPRETER: True,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pro",
                CONF_TEMPERATURE: 1.0,
                CONF_CHAT_MODEL: "o1-pro",
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_MAX_TOKENS: 10000,
                CONF_STORE_RESPONSES: False,
                CONF_REASONING_EFFORT: "high",
                CONF_REASONING_SUMMARY: RECOMMENDED_REASONING_SUMMARY,
                CONF_CODE_INTERPRETER: True,
            },
        ),
        (  # options for web search without user location
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "bla",
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.3,
                    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                    CONF_TOP_P: RECOMMENDED_TOP_P,
                    CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                },
                {
                    CONF_WEB_SEARCH: True,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                    CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                    CONF_SERVICE_TIER: "auto",
                    CONF_CODE_INTERPRETER: False,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_STORE_RESPONSES: False,
                CONF_SERVICE_TIER: "auto",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_CODE_INTERPRETER: False,
            },
        ),
        # Test that current options are showed as suggested values
        (  # Case 1: web search
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like super Mario",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-4o",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: True,
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_SERVICE_TIER: "auto",
                CONF_CODE_INTERPRETER: True,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like super Mario",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "gpt-4o",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                    CONF_STORE_RESPONSES: True,
                },
                {
                    CONF_WEB_SEARCH: True,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                    CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                    CONF_SERVICE_TIER: "default",
                    CONF_CODE_INTERPRETER: True,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like super Mario",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-4o",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: True,
                CONF_SERVICE_TIER: "default",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_CODE_INTERPRETER: True,
            },
        ),
        (  # Case 2: reasoning model
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "low",
                CONF_REASONING_SUMMARY: "auto",
                CONF_VERBOSITY: "high",
                CONF_CODE_INTERPRETER: False,
                CONF_SERVICE_TIER: "flex",
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "gpt-5.6",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                },
                {
                    CONF_REASONING_EFFORT: "max",
                    CONF_REASONING_SUMMARY: RECOMMENDED_REASONING_SUMMARY,
                    CONF_CODE_INTERPRETER: False,
                    CONF_VERBOSITY: "high",
                    CONF_SERVICE_TIER: "flex",
                    CONF_WEB_SEARCH: False,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                    CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                    CONF_PRO_MODE: True,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5.6",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: False,
                CONF_REASONING_EFFORT: "max",
                CONF_REASONING_SUMMARY: RECOMMENDED_REASONING_SUMMARY,
                CONF_CODE_INTERPRETER: False,
                CONF_VERBOSITY: "high",
                CONF_SERVICE_TIER: "flex",
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_PRO_MODE: True,
            },
        ),
        # Test that old options are removed after reconfiguration
        (  # Case 1: web search to recommended
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-4o",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_CODE_INTERPRETER: True,
                CONF_SERVICE_TIER: "priority",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
            },
            (
                {
                    CONF_RECOMMENDED: True,
                    CONF_LLM_HASS_API: ["assist"],
                    CONF_PROMPT: "",
                },
            ),
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
                CONF_PROMPT: "",
            },
        ),
        (  # Case 2: reasoning to recommended
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "high",
                CONF_SERVICE_TIER: "auto",
                CONF_CODE_INTERPRETER: True,
                CONF_VERBOSITY: "low",
                CONF_WEB_SEARCH: False,
            },
            (
                {
                    CONF_RECOMMENDED: True,
                    CONF_PROMPT: "Speak like a pirate",
                },
            ),
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "Speak like a pirate",
            },
        ),
        (  # Case 3: web search to reasoning
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-4o",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_SERVICE_TIER: "auto",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_CODE_INTERPRETER: True,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "o3-mini",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                },
                {
                    CONF_REASONING_EFFORT: "low",
                    CONF_CODE_INTERPRETER: True,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "o3-mini",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: False,
                CONF_REASONING_EFFORT: "low",
                CONF_REASONING_SUMMARY: RECOMMENDED_REASONING_SUMMARY,
                CONF_CODE_INTERPRETER: True,
            },
        ),
        (  # Case 4: reasoning to web search
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5.6",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "low",
                CONF_REASONING_SUMMARY: "auto",
                CONF_SERVICE_TIER: "flex",
                CONF_CODE_INTERPRETER: True,
                CONF_VERBOSITY: "medium",
                CONF_PRO_MODE: True,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "gpt-4o",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                },
                {
                    CONF_WEB_SEARCH: True,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                    CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                    CONF_SERVICE_TIER: "priority",
                    CONF_CODE_INTERPRETER: False,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-4o",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: False,
                CONF_SERVICE_TIER: "priority",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                CONF_CODE_INTERPRETER: False,
            },
        ),
        (  # Case 5: code interpreter supported to not supported model
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "low",
                CONF_REASONING_SUMMARY: "auto",
                CONF_CODE_INTERPRETER: True,
                CONF_VERBOSITY: "medium",
                CONF_SERVICE_TIER: "auto",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "gpt-5-pro",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                },
                {
                    CONF_WEB_SEARCH: True,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                    CONF_WEB_SEARCH_INLINE_CITATIONS: True,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5-pro",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_STORE_RESPONSES: False,
                CONF_REASONING_SUMMARY: RECOMMENDED_REASONING_SUMMARY,
                CONF_VERBOSITY: "medium",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
            },
        ),
        (
            {},
            (
                {CONF_RECOMMENDED: False},
                {CONF_CHAT_MODEL: "gpt-6-astra"},
                {
                    CONF_REASONING_EFFORT: "max",
                    CONF_REASONING_SUMMARY: "detailed",
                    CONF_PRO_MODE: True,
                    CONF_VERBOSITY: "low",
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_CHAT_MODEL: "gpt-6-astra",
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TEMPERATURE: 1.0,
                CONF_STORE_RESPONSES: False,
                CONF_CODE_INTERPRETER: False,
                CONF_REASONING_EFFORT: "max",
                CONF_REASONING_SUMMARY: "detailed",
                CONF_PRO_MODE: True,
                CONF_VERBOSITY: "low",
                CONF_SERVICE_TIER: "auto",
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
                CONF_WEB_SEARCH_USER_LOCATION: False,
                CONF_WEB_SEARCH_INLINE_CITATIONS: False,
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_subentry_switching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    current_options: dict[str, str | float | bool | list[str]],
    new_options: tuple[dict[str, str | float | bool | list[str]], ...],
    expected_options: dict[str, str | float | bool | list[str]],
) -> None:
    """Test the subentry form."""
    subentry = next(
        sub
        for sub in mock_config_entry.subentries.values()
        if sub.subentry_type == "conversation"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=current_options
    )
    await hass.async_block_till_done()
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["step_id"] == "init"

    for step_options in new_options:
        assert subentry_flow["type"] is FlowResultType.FORM

        # Test that current options are showed as suggested values:
        for key in subentry_flow["data_schema"].schema:
            if (
                isinstance(key.description, dict)
                and "suggested_value" in key.description
                and key in current_options
            ):
                current_option = current_options[key]
                if key == CONF_LLM_HASS_API and isinstance(current_option, str):
                    current_option = [current_option]
                assert key.description["suggested_value"] == current_option

        # Configure current step
        subentry_flow = await hass.config_entries.subentries.async_configure(
            subentry_flow["flow_id"],
            step_options,
        )
        await hass.async_block_till_done()

    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"
    assert subentry.data == expected_options


@pytest.mark.parametrize("store_responses", [False, True])
async def test_subentry_web_search_user_location(
    hass: HomeAssistant,
    mock_config_entry,
    mock_init_component,
    store_responses: bool,
) -> None:
    """Test fetching user location."""
    subentry = next(
        sub
        for sub in mock_config_entry.subentries.values()
        if sub.subentry_type == "conversation"
    )
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "additional"

    # Configure additional step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            CONF_STORE_RESPONSES: store_responses,
        },
    )
    await hass.async_block_till_done()
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "model"

    hass.config.country = "US"
    hass.config.time_zone = "America/Los_Angeles"
    hass.states.async_set(
        "zone.home", "0", {"latitude": 37.7749, "longitude": -122.4194}
    )
    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = Response(
            object="response",
            id="resp_A",
            created_at=1700000000,
            model="gpt-4o-mini",
            parallel_tool_calls=True,
            tool_choice="auto",
            tools=[],
            output=[
                ResponseOutputMessage(
                    type="message",
                    id="msg_A",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text='{"city": "San Francisco", "region": "California"}',
                            annotations=[],
                        )
                    ],
                    role="assistant",
                    status="completed",
                )
            ],
        )

        # Configure model step
        subentry_flow = await hass.config_entries.subentries.async_configure(
            subentry_flow["flow_id"],
            {
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
                CONF_WEB_SEARCH_USER_LOCATION: True,
            },
        )
        await hass.async_block_till_done()
    assert (
        mock_create.call_args.kwargs["input"][0]["content"] == "Where are the following"
        " coordinates located: (37.7749, -122.4194)?"
    )
    assert mock_create.call_args.kwargs["store"] is store_responses
    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 1.0,
        CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
        CONF_TOP_P: RECOMMENDED_TOP_P,
        CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        CONF_SERVICE_TIER: "auto",
        CONF_STORE_RESPONSES: store_responses,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
        CONF_WEB_SEARCH_USER_LOCATION: True,
        CONF_WEB_SEARCH_CITY: "San Francisco",
        CONF_WEB_SEARCH_REGION: "California",
        CONF_WEB_SEARCH_COUNTRY: "US",
        CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        CONF_WEB_SEARCH_INLINE_CITATIONS: False,
        CONF_CODE_INTERPRETER: False,
    }


async def test_creating_ai_task_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating an AI task subentry."""
    old_subentries = set(mock_config_entry.subentries)
    # Original conversation + ai_task + stt + tts
    assert len(mock_config_entry.subentries) == 4

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert not result.get("errors")

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Custom AI Task",
            CONF_RECOMMENDED: True,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Custom AI Task"
    assert result2.get("data") == {
        CONF_RECOMMENDED: True,
    }

    assert (
        len(mock_config_entry.subentries) == 5
    )  # Original conversation + stt + tts + ai_task + new ai_task

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "ai_task_data"
    assert new_subentry.title == "Custom AI Task"


async def test_ai_task_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an AI task subentry when entry is not loaded."""
    # Don't call mock_init_component to simulate not loaded state
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("image_options", "image_model"),
    [
        ({}, "gpt-image-2.5-flare"),
        (
            {CONF_IMAGE_MODEL: "gpt-image-2.5-sunburst"},
            "gpt-image-2.5-sunburst",
        ),
        (
            {CONF_IMAGE_MODEL: "gpt-image-2.5-flare"},
            "gpt-image-2.5-flare",
        ),
        ({CONF_IMAGE_MODEL: "gpt-image-2"}, "gpt-image-2"),
    ],
)
async def test_creating_ai_task_subentry_additional(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    image_options: dict[str, str],
    image_model: str,
) -> None:
    """Test creating an AI task subentry with additional settings."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Go to additional settings
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Advanced AI Task",
            CONF_RECOMMENDED: False,
        },
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "additional"

    # Configure additional settings
    result3 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4o",
            CONF_MAX_TOKENS: 200,
            CONF_STORE_RESPONSES: True,
            CONF_TEMPERATURE: 0.5,
            CONF_TOP_P: 0.9,
        },
    )

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("step_id") == "model"

    # Configure model settings
    result4 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_CODE_INTERPRETER: False,
            **image_options,
        },
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "Advanced AI Task"
    assert result4.get("data") == {
        CONF_RECOMMENDED: False,
        CONF_CHAT_MODEL: "gpt-4o",
        CONF_IMAGE_MODEL: image_model,
        CONF_MAX_TOKENS: 200,
        CONF_STORE_RESPONSES: True,
        CONF_TEMPERATURE: 0.5,
        CONF_TOP_P: 0.9,
        CONF_CODE_INTERPRETER: False,
        CONF_SERVICE_TIER: "auto",
        CONF_WEB_SEARCH: False,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
        CONF_WEB_SEARCH_USER_LOCATION: False,
        CONF_WEB_SEARCH_INLINE_CITATIONS: False,
    }


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("model", "has_web_search"),
    [
        ("gpt-4o", True),
        ("gpt-5.6", True),
        ("gpt-6-luna", True),
        ("gpt-6-astra", True),
        ("gpt-6.1-sol", True),
        ("o3", True),
        ("gpt-3.5-turbo", False),
        ("gpt-4-turbo", False),
        ("gpt-4.1-nano-2025-04-14", False),
        ("o1", False),
        ("o3-mini", False),
    ],
)
async def test_ai_task_web_search_supported_models(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model: str,
    has_web_search: bool,
) -> None:
    """Expose task search for models outside the existing exclusion list."""
    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_RECOMMENDED: False}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHAT_MODEL: model}
    )
    assert result["step_id"] == "model"
    assert (CONF_WEB_SEARCH in result["data_schema"].schema) == has_web_search
    assert (
        CONF_WEB_SEARCH_CONTEXT_SIZE in result["data_schema"].schema
    ) == has_web_search
    assert (
        CONF_WEB_SEARCH_USER_LOCATION in result["data_schema"].schema
    ) == has_web_search


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6-astra", "gpt-6.1-sol"])
@pytest.mark.parametrize("web_search", [False, True])
async def test_ai_task_gpt6_saved_search_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model: str,
    web_search: bool,
) -> None:
    """Save both tool settings through the native task configuration flow."""
    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_RECOMMENDED: False}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHAT_MODEL: model}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_REASONING_EFFORT: "low",
            CONF_WEB_SEARCH: web_search,
            CONF_CODE_INTERPRETER: True,
        },
    )
    assert result["reason"] == "reconfigure_successful"
    saved = mock_config_entry.subentries[subentry.subentry_id].data
    assert saved[CONF_CHAT_MODEL] == model
    assert saved[CONF_REASONING_EFFORT] == "low"
    assert saved[CONF_WEB_SEARCH] == web_search
    assert saved[CONF_CODE_INTERPRETER] is True


async def test_creating_stt_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating a STT subentry."""
    old_subentries = set(mock_config_entry.subentries)
    # Original conversation + ai_task + stt + tts
    assert len(mock_config_entry.subentries) == 4

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert not result.get("errors")

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Custom STT",
            CONF_PROMPT: (
                "Umm, let me think like, hmm\u2026 Okay,"
                " here’s what I’m, like, thinking."
            ),
            CONF_CHAT_MODEL: "gpt-4o-transcribe",
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Custom STT"
    assert result.get("data") == {
        CONF_PROMPT: (
            "Umm, let me think like, hmm\u2026 Okay, here’s what I’m, like, thinking."
        ),
        CONF_CHAT_MODEL: "gpt-4o-transcribe",
    }

    assert (
        len(mock_config_entry.subentries) == 5
    )  # Original conversation + ai_task + tts + original stt + new stt

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "stt"
    assert new_subentry.title == "Custom STT"


async def test_stt_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a STT subentry when entry is not loaded."""
    # Don't call mock_init_component to simulate not loaded state
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"


async def test_stt_reconfigure(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test reconfiguring the STT subentry updates prompt and chat model."""
    subentry = [
        s for s in mock_config_entry.subentries.values() if s.subentry_type == "stt"
    ][0]
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            "prompt": "This is a conversation about smart pirate ships.",
            "chat_model": "gpt-4o-mini-transcribe-2025-12-15",
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data["prompt"] == "This is a conversation about smart pirate ships."
    assert subentry.data["chat_model"] == "gpt-4o-mini-transcribe-2025-12-15"


async def test_creating_tts_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating a TTS subentry."""
    old_subentries = set(mock_config_entry.subentries)
    # Original conversation + ai_task + stt + tts
    assert len(mock_config_entry.subentries) == 4

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert not result.get("errors")

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Custom TTS",
            CONF_PROMPT: "Speak like a drunk pirate",
            CONF_TTS_SPEED: 0.85,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Custom TTS"
    assert result.get("data") == {
        CONF_PROMPT: "Speak like a drunk pirate",
        CONF_TTS_SPEED: 0.85,
        CONF_CHAT_MODEL: "gpt-4o-mini-tts",
    }

    assert (
        len(mock_config_entry.subentries) == 5
    )  # Original conversation + ai_task + stt + tts + new tts

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "tts"
    assert new_subentry.title == "Custom TTS"


async def test_tts_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a TTS subentry when entry is not loaded."""
    # Don't call mock_init_component to simulate not loaded state
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"


async def test_tts_reconfigure(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the tts subentry reconfigure flow."""
    subentry = [
        s for s in mock_config_entry.subentries.values() if s.subentry_type == "tts"
    ][0]
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "tts_speed": 0.5,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data["prompt"] == "Speak like a pirate"
    assert subentry.data["tts_speed"] == 0.5


async def test_reauth(hass: HomeAssistant) -> None:
    """Test we can reauthenticate."""
    # Pretend we already set up a config entry.
    hass.config.components.add("openai_conversation")
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    )

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    # The same auth method choice as when adding the integration is offered.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"
    assert set(result["data_schema"].schema) == {CONF_AUTH_METHOD}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert set(result["data_schema"].schema) == {CONF_API_KEY}

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.openai_conversation.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new_api_key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


@pytest.mark.usefixtures("mock_init_component")
async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the API key can be reconfigured."""
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"
    assert set(result["data_schema"].schema) == {CONF_AUTH_METHOD}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert set(result["data_schema"].schema) == {CONF_API_KEY}

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as mock_async_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
    assert mock_async_reload.call_count == 1


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an invalid API key is rejected during reconfiguration."""
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )

    assert result["step_id"] == "reconfigure"
    assert set(result["data_schema"].schema) == {CONF_API_KEY}

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        side_effect=AuthenticationError(
            response=httpx2.Response(status_code=None, request=""),
            body=None,
            message=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "invalid_api_key"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_config_entry.data[CONF_API_KEY] == "bla"

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reauth_switch_to_chatgpt(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test an API key entry can be switched to the ChatGPT plan on reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_CONVERSATION_OPTIONS,
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_AI_TASK_OPTIONS,
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_STT_OPTIONS,
                subentry_type="stt",
                title=DEFAULT_STT_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_TTS_OPTIONS,
                subentry_type="tts",
                title=DEFAULT_TTS_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "chatgpt"

    params = dict(
        parse_qsl(urlparse(result["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models_for_credentials",
            AsyncMock(return_value=CHATGPT_CATALOG),
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CALLBACK_URL: (
                    f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                    f"&client_id={CHATGPT_CLIENT_ID}"
                )
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # The entry is now a plan entry, bound to the signed in account.
    assert entry.data[CONF_AUTH_METHOD] == AUTH_METHOD_CHATGPT
    assert CONF_API_KEY not in entry.data
    assert entry.unique_id == f"chatgpt-user-1:{CHATGPT_CLIENT_ID}"

    # The plan usage route has neither speech to text nor text to speech, so
    # those subentries are removed. The remaining ones must not fall back to
    # the API default model.
    assert {s.subentry_type for s in entry.subentries.values()} == {
        "conversation",
        "ai_task_data",
    }
    assert all(
        subentry.data[CONF_CHAT_MODEL] == CHATGPT_CATALOG[0]
        for subentry in entry.subentries.values()
    )


async def test_reconfigure_chatgpt_entry_switches_to_api_key(
    hass: HomeAssistant,
) -> None:
    """Test a ChatGPT plan entry can be switched back to an API key."""
    entry = _chatgpt_config_entry(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"
    assert set(result["data_schema"].schema) == {CONF_AUTH_METHOD}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert set(result["data_schema"].schema) == {CONF_API_KEY}

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The whole data layout is replaced and the account scoped id is dropped.
    assert entry.data == {CONF_API_KEY: "new_api_key"}
    assert entry.unique_id is None

    # The API key entry still sets up.
    with patch("openai.resources.models.AsyncModels.list", new_callable=AsyncMock):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("current_llm_apis", "suggested_llm_apis", "expected_options"),
    [
        ("assist", ["assist"], ["assist", "homeassistant"]),
        (["assist"], ["assist"], ["assist", "homeassistant"]),
        ("non-existent", [], ["assist", "homeassistant"]),
        (["non-existent"], [], ["assist", "homeassistant"]),
        (["assist", "non-existent"], ["assist"], ["assist", "homeassistant"]),
        pytest.param(
            ["homeassistant"],
            ["homeassistant"],
            ["assist", "homeassistant"],
            id="homeassistant_list",
        ),
    ],
)
async def test_reconfigure_conversation_subentry_llm_api_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    current_llm_apis: list[str],
    suggested_llm_apis: list[str],
    expected_options: list[str],
) -> None:
    """Test llm_hass_api field values when reconfiguring a conversation subentry."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_LLM_HASS_API: current_llm_apis},
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.AsyncOpenAI.models",
    ):
        subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )

    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Only valid LLM APIs should be suggested and shown as options
    schema = subentry_flow["data_schema"].schema
    key = next(k for k in schema if k == CONF_LLM_HASS_API)
    assert key.description
    assert key.description.get("suggested_value") == suggested_llm_apis
    field_schema = schema[key]
    assert field_schema.config
    assert [
        opt["value"] for opt in field_schema.config.get("options")
    ] == expected_options


# --- Sign in with ChatGPT ---------------------------------------------------

CHATGPT_CLIENT_ID = f"{CLIENT_ID_PREFIX}test123"
CHATGPT_SCOPE = f"{PLAN_SCOPE} email offline_access openid profile resource.invoke"


def _siwc_response(status_code: int = 200, json_data: Any = None) -> MagicMock:
    """Create a mocked httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data if json_data is not None else {})
    return response


@pytest.fixture
def mock_siwc_client() -> Generator[MagicMock]:
    """Patch the httpx client used by the SIWC helpers."""
    client = MagicMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    with patch(
        "homeassistant.components.openai_conversation.chatgpt_auth.get_async_client",
        return_value=client,
    ):
        yield client


def _chatgpt_entry_data(**kwargs: Any) -> dict[str, Any]:
    """Create config entry data for a ChatGPT subscription entry."""
    return {
        CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT,
        CONF_CLIENT_ID: CHATGPT_CLIENT_ID,
        CONF_EXT_AGENT_HOST_ID: "urn:uuid:00000000-0000-4000-8000-000000000000",
        CONF_SUB: "chatgpt-user-1",
        CONF_ACCESS_TOKEN: "access-1",
        "refresh_token": "refresh-1",
        CONF_ID_TOKEN: "id-1",
        "expires_at": "2030-01-01T00:00:00+00:00",
        CONF_SCOPES: CHATGPT_SCOPE.split(),
        **kwargs,
    }


def _chatgpt_token_response(
    private_key: Any, nonce: str, **kwargs: Any
) -> dict[str, Any]:
    """Create a token endpoint response for a successful sign in."""
    token = {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "id_token": create_chatgpt_id_token(
            private_key, client_id=CHATGPT_CLIENT_ID, nonce=nonce
        ),
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": CHATGPT_SCOPE,
    }
    token.update(kwargs)
    return token


async def _async_start_chatgpt_flow(hass: HomeAssistant) -> dict[str, Any]:
    """Start the config flow and pick the ChatGPT auth method."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "chatgpt"
    return result


async def test_chatgpt_flow(hass: HomeAssistant, mock_siwc_client: MagicMock) -> None:
    """Test the complete Sign in with ChatGPT flow."""
    form = await _async_start_chatgpt_flow(hass)

    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    assert params["client_id"] == DYNAMIC_AGENT_CLIENT
    assert params["agent_name_hint"] == "Home Assistant"
    assert params["ext_agent_host_id"].startswith("urn:uuid:")

    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200,
        _chatgpt_token_response(
            private_key,
            params["nonce"],
            earliest_refresh_at="2030-01-01T00:00:00+00:00",
        ),
    )

    with (
        patch(
            "homeassistant.components.openai_conversation.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models_for_credentials",
            AsyncMock(return_value=CHATGPT_CATALOG),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {
                CONF_CALLBACK_URL: (
                    f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                    f"&scope=chatgpt.tokens.use.direct&client_id={CHATGPT_CLIENT_ID}"
                )
            },
        )
        await hass.async_block_till_done()

        # The entry is not created before the user picked a model of the account.
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "chatgpt_model"
        assert set(result["data_schema"].schema) == {CONF_CHAT_MODEL}
        assert (
            result["data_schema"].schema[CONF_CHAT_MODEL].config["options"]
            == CHATGPT_CATALOG
        )

        # The first catalog entry is the default, so an empty submit picks it.
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ChatGPT subscription"
    # The host id is generated per installation, so compare it separately.
    data = dict(result["data"])
    host_id = data["ext_agent_host_id"]
    assert host_id.startswith("urn:uuid:")
    # The expiry is derived from the token response, so check it on its own.
    issued_at = dt_util.utcnow()
    expires_at = dt_util.parse_datetime(data.pop("expires_at"))
    assert expires_at is not None
    assert issued_at < expires_at < issued_at + timedelta(hours=2)
    expected = _chatgpt_entry_data(
        ext_agent_host_id=host_id,
        id_token=mock_siwc_client.post.return_value.json.return_value["id_token"],
        earliest_refresh_at="2030-01-01T00:00:00+00:00",
        email="user@example.com",
    )
    expected.pop("expires_at")
    assert data == expected
    # The issued client id replaces `dynamic_agent_client` and is reused later.
    assert mock_siwc_client.post.call_args.args[0] == TOKEN_URL
    assert mock_siwc_client.post.call_args.kwargs["data"]["client_id"] == (
        CHATGPT_CLIENT_ID
    )
    assert mock_siwc_client.post.call_args.kwargs["data"]["grant_type"] == (
        "authorization_code"
    )

    # ChatGPT plan usage does not support speech to text or text to speech,
    # and the plan route rejects the API default model.
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": {
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_CHAT_MODEL: CHATGPT_CATALOG[0],
            },
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": {
                **RECOMMENDED_AI_TASK_OPTIONS,
                CONF_CHAT_MODEL: CHATGPT_CATALOG[0],
            },
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
    ]

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == f"chatgpt-user-1:{CHATGPT_CLIENT_ID}"
    assert entry.data[CONF_AUTH_METHOD] == AUTH_METHOD_CHATGPT
    # The stored subentries carry a model of the account catalog, never the
    # API default the plan route rejects.
    assert all(
        subentry.data[CONF_CHAT_MODEL] == CHATGPT_CATALOG[0]
        for subentry in entry.subentries.values()
    )


async def test_chatgpt_flow_catalog_unavailable(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test the sign in offers a text field when the catalog cannot be read.

    The catalog is not needed to complete the sign in (OpenAI answered a
    transient 520 while this was written). The user types a model instead, and
    the entry is still created with it.
    """
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    with (
        patch(
            "homeassistant.components.openai_conversation.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models_for_credentials",
            AsyncMock(side_effect=HomeAssistantError("HTTP 520")),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {
                CONF_CALLBACK_URL: (
                    f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                    f"&client_id={CHATGPT_CLIENT_ID}"
                )
            },
        )
        await hass.async_block_till_done()

        # The unreadable catalog does not fail the sign in: the model is chosen
        # from the suggestions instead of the API default the plan rejects.
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "chatgpt_model"
        assert set(result["data_schema"].schema) == {CONF_CHAT_MODEL}
        selector = result["data_schema"].schema[CONF_CHAT_MODEL]
        assert isinstance(selector, SelectSelector)
        assert selector.config["options"] == SUBSCRIPTION_MODEL_SUGGESTIONS
        assert selector.config["custom_value"] is True

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CHAT_MODEL: CHATGPT_CATALOG[0]}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert all(
        subentry["data"][CONF_CHAT_MODEL] == CHATGPT_CATALOG[0]
        for subentry in result["subentries"]
    )


async def test_chatgpt_flow_already_configured(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test that the same ChatGPT account cannot be added twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    ).add_to_hass(hass)

    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("?error=access_denied&state={state}", "access_denied"),
        ("?code=the-code&state=wrong-state", "invalid_state"),
        ("?state={state}", "invalid_callback_url"),
        (
            f"?code=the-code&state={{state}}&error=&client_id={CHATGPT_CLIENT_ID}",
            None,
        ),
    ],
)
async def test_chatgpt_flow_callback_errors(
    hass: HomeAssistant,
    mock_siwc_client: MagicMock,
    query: str,
    error: str | None,
) -> None:
    """Test invalid callbacks are reported instead of exchanging a code."""
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {CONF_CALLBACK_URL: f"{REDIRECT_URI}{query.format(state=params['state'])}"},
    )

    if error is None:
        # `error=` is empty and therefore not an error: the code is exchanged.
        # The rest of the sign in is covered by `test_chatgpt_flow`.
        assert mock_siwc_client.post.call_count == 1
    else:
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "chatgpt"
        assert result["errors"] == {"base": error}
        assert mock_siwc_client.post.call_count == 0


async def test_chatgpt_flow_registration_incomplete(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test that a new registration without an issued client id fails."""
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                "&client_id=not_an_issued_client"
            )
        },
    )

    assert result["errors"] == {"base": "registration_incomplete"}
    assert mock_siwc_client.post.call_count == 0


async def test_chatgpt_flow_plan_usage_not_granted(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test that a sign in without the plan scope is aborted."""
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )

    mock_siwc_client.post.return_value = _siwc_response(
        200,
        {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_in": 3600,
            "scope": "email openid profile",
        },
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "plan_usage_not_granted"


async def test_chatgpt_flow_invalid_id_token(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test that an ID token for another nonce is rejected."""
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )

    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, "other-nonce")
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_chatgpt_flow_token_exchange_failed(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test a failing code exchange."""
    form = await _async_start_chatgpt_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    mock_siwc_client.post.return_value = _siwc_response(400, {"error": "invalid_grant"})

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_api_key_is_required_for_api_key_auth(hass: HomeAssistant) -> None:
    """Test the API key form still requires an API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["step_id"] == "api_key"

    # A blank form field is submitted as an empty string, not as a missing key.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"
    assert result["errors"] == {CONF_API_KEY: "api_key_required"}


async def test_chatgpt_entry_subentry_types(hass: HomeAssistant) -> None:
    """Test which subentries a ChatGPT entry supports."""
    entry = MockConfigEntry(domain=DOMAIN, data=_chatgpt_entry_data())
    entry.add_to_hass(hass)

    assert set(OpenAIConfigFlow.async_get_supported_subentry_types(entry)) == {
        "conversation",
        "ai_task_data",
    }

    api_key_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "bla"})
    api_key_entry.add_to_hass(hass)
    assert set(OpenAIConfigFlow.async_get_supported_subentry_types(api_key_entry)) == {
        "conversation",
        "ai_task_data",
        "stt",
        "tts",
    }


async def test_chatgpt_reauth(hass: HomeAssistant, mock_siwc_client: MagicMock) -> None:
    """Test that reauth reuses the saved registration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "chatgpt"

    params = dict(
        parse_qsl(urlparse(result["description_placeholders"]["auth_url"]).query)
    )
    assert params["client_id"] == CHATGPT_CLIENT_ID
    assert params["id_token_hint"] == "id-1"
    assert "agent_name_hint" not in params

    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200,
        _chatgpt_token_response(private_key, params["nonce"], access_token="access-2"),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CALLBACK_URL: (f"{REDIRECT_URI}?code=the-code&state={params['state']}")},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "access-2"


@pytest.mark.usefixtures("mock_init_component")
async def test_switch_to_chatgpt_removes_speech_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_siwc_client: MagicMock,
) -> None:
    """Test the speech entities of a converted entry are not recreated."""
    entity_reg = er.async_get(hass)

    def _entities() -> set[str]:
        return {
            reg_entry.entity_id
            for reg_entry in er.async_entries_for_config_entry(
                entity_reg, mock_config_entry.entry_id
            )
        }

    speech = {
        entity_id
        for entity_id in _entities()
        if entity_id.split(".")[0] in ("stt", "tts")
    }
    assert speech

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT}
    )
    params = dict(
        parse_qsl(urlparse(result["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    # Both the flow and the reload that follows the conversion need the catalog.
    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models_for_credentials",
            AsyncMock(return_value=CHATGPT_CATALOG),
        ),
        patch(
            "homeassistant.components.openai_conversation.async_get_subscription_models",
            AsyncMock(return_value=CHATGPT_CATALOG),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CALLBACK_URL: (
                    f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                    f"&client_id={CHATGPT_CLIENT_ID}"
                )
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert CONF_API_KEY not in mock_config_entry.data
    # The speech entities of the removed subentries are gone and the reload
    # does not bring them back.
    assert not (speech & _entities())


# Catalog slugs the live route serves to a ChatGPT plan account.
CHATGPT_CATALOG = ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol"]


def _chatgpt_config_entry(
    hass: HomeAssistant, *, chat_model: str | None = None
) -> MockConfigEntry:
    """Create a ChatGPT subscription config entry with conversation subentries."""
    conversation_data = dict(RECOMMENDED_CONVERSATION_OPTIONS)
    if chat_model is not None:
        conversation_data[CONF_CHAT_MODEL] = chat_model
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ChatGPT subscription",
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        version=2,
        minor_version=7,
        data=_chatgpt_entry_data(),
        subentries_data=[
            config_entries.ConfigSubentryData(
                data=conversation_data,
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_AI_TASK_OPTIONS,
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry


def _mock_catalog(models: list[str]) -> Any:
    """Patch the model catalog both while setting up and in the flow."""
    return (
        patch(
            "homeassistant.components.openai_conversation.async_get_subscription_models",
            AsyncMock(return_value=models),
        ),
        patch(
            "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models",
            AsyncMock(return_value=models),
        ),
    )


async def test_chatgpt_subentry_chat_model_selector(hass: HomeAssistant) -> None:
    """Test the chat model selector of a ChatGPT subscription subentry."""
    entry = _chatgpt_config_entry(hass)
    setup_patch, flow_patch = _mock_catalog(CHATGPT_CATALOG)

    with setup_patch, flow_patch:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state is config_entries.ConfigEntryState.LOADED

        subentry = next(iter(entry.subentries.values()))
        result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_RECOMMENDED: False}
        )
        assert result["step_id"] == "additional"

        # The selector offers the catalog slugs.
        field_schema = result["data_schema"].schema[CONF_CHAT_MODEL]
        assert field_schema.config["options"] == CHATGPT_CATALOG

        # The default is the first catalog slug.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "model"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert subentry.data[CONF_CHAT_MODEL] == CHATGPT_CATALOG[0]


async def test_chatgpt_subentry_model_not_supported(hass: HomeAssistant) -> None:
    """Test a model outside the catalog is rejected."""
    entry = _chatgpt_config_entry(hass)
    setup_patch, flow_patch = _mock_catalog(CHATGPT_CATALOG)

    with setup_patch, flow_patch:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state is config_entries.ConfigEntryState.LOADED

        subentry = next(iter(entry.subentries.values()))
        result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_RECOMMENDED: False}
        )
        assert result["step_id"] == "additional"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_CHAT_MODEL: "model_not_supported"}


async def test_chatgpt_subentry_model_accepted_when_catalog_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test a model is accepted when the catalog cannot be read.

    An unreadable catalog says nothing about the model the user submits, so
    the model is stored instead of being rejected as unsupported.
    """
    entry = _chatgpt_config_entry(hass)
    setup_patch, _ = _mock_catalog(CHATGPT_CATALOG)

    with setup_patch:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state is config_entries.ConfigEntryState.LOADED

    subentry = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )

    with patch(
        "homeassistant.components.openai_conversation.config_flow.async_get_subscription_models",
        AsyncMock(side_effect=HomeAssistantError("HTTP 520")),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_RECOMMENDED: False}
        )
        assert result["step_id"] == "additional"

        # The unreadable catalog must not reject the submitted model.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_CHAT_MODEL: CHATGPT_CATALOG[0]}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "model"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        entry.subentries[subentry.subentry_id].data[CONF_CHAT_MODEL]
        == CHATGPT_CATALOG[0]
    )


# --- Patch coverage for the Sign in with ChatGPT flows ----------------------


def _chatgpt_callback(form: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Return the flow id and the callback URL of a started chatgpt step."""
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    url = (
        f"{REDIRECT_URI}?code=the-code&state={params['state']}"
        f"&client_id={CHATGPT_CLIENT_ID}"
    )
    return form["flow_id"], {CONF_CALLBACK_URL: url}


async def test_chatgpt_flow_callback_unexpected_error(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test an unexpected failure while completing the sign in is shown."""
    form = await _async_start_chatgpt_flow(hass)

    with patch(
        "homeassistant.components.openai_conversation.config_flow.async_token_request",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(
            *_chatgpt_callback(form)
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "chatgpt"
    assert result["errors"] == {"base": "unexpected_error"}


async def test_chatgpt_flow_missing_id_token(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test a plan sign in without an ID token is rejected."""
    form = await _async_start_chatgpt_flow(hass)
    mock_siwc_client.post.return_value = _siwc_response(
        200,
        {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_in": 3600,
            "scope": CHATGPT_SCOPE,
        },
    )

    result = await hass.config_entries.flow.async_configure(*_chatgpt_callback(form))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_chatgpt_reauth_client_id_mismatch(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test a callback naming another client id is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    )
    entry.add_to_hass(hass)

    form = await entry.start_reauth_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CLIENT_ID_PREFIX}other"
            )
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "client_id_mismatch"}
    assert mock_siwc_client.post.call_count == 0


async def test_chatgpt_reauth_wrong_account(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test reauthenticating with another account is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    )
    entry.add_to_hass(hass)

    form = await entry.start_reauth_flow(hass)
    params = dict(
        parse_qsl(urlparse(form["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200,
        _chatgpt_token_response(
            private_key,
            params["nonce"],
            id_token=create_chatgpt_id_token(
                private_key,
                client_id=CHATGPT_CLIENT_ID,
                nonce=params["nonce"],
                sub="chatgpt-user-2",
            ),
        ),
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}


async def test_reconfigure_chatgpt_entry_aborts_on_known_account(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test reconfiguring onto an account of another entry is aborted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"legacy:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"chatgpt-user-1:{CHATGPT_CLIENT_ID}",
        data=_chatgpt_entry_data(),
    ).add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "auth_method"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT}
    )
    assert result["step_id"] == "chatgpt"

    params = dict(
        parse_qsl(urlparse(result["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALLBACK_URL: (
                f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                f"&client_id={CHATGPT_CLIENT_ID}"
            )
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_loaded_chatgpt_entry_switches_to_api_key(
    hass: HomeAssistant,
) -> None:
    """Test a loaded plan entry switches to an API key."""
    entry = _chatgpt_config_entry(hass)
    setup_patch, _ = _mock_catalog(CHATGPT_CATALOG)
    with setup_patch:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
    # The loaded entry has an update listener, so the switch aborts the update.
    assert entry.update_listeners

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_API_KEY}
    )
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id is None


async def test_reconfigure_api_key_entry_catalog_failure(
    hass: HomeAssistant, mock_siwc_client: MagicMock
) -> None:
    """Test converting an API key entry when the catalog cannot be read."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_CONVERSATION_OPTIONS,
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data=RECOMMENDED_AI_TASK_OPTIONS,
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT}
    )
    assert result["step_id"] == "chatgpt"

    params = dict(
        parse_qsl(urlparse(result["description_placeholders"]["auth_url"]).query)
    )
    private_key = create_chatgpt_rsa_key()
    mock_siwc_client.get.return_value = _siwc_response(
        200, create_chatgpt_jwks(private_key)
    )
    mock_siwc_client.post.return_value = _siwc_response(
        200, _chatgpt_token_response(private_key, params["nonce"])
    )

    with patch.object(
        OpenAIConfigFlow,
        "_async_catalog_default",
        AsyncMock(side_effect=HomeAssistantError("HTTP 520")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CALLBACK_URL: (
                    f"{REDIRECT_URI}?code=the-code&state={params['state']}"
                    f"&client_id={CHATGPT_CLIENT_ID}"
                )
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def _async_reach_subentry_model_step(
    hass: HomeAssistant, entry: MockConfigEntry, *patches: Any
) -> dict[str, Any]:
    """Drive a conversation subentry reconfigure flow to the model step."""
    with ExitStack() as stack:
        for manager in patches:
            stack.enter_context(manager)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state is config_entries.ConfigEntryState.LOADED

        subentry = next(
            sub
            for sub in entry.subentries.values()
            if sub.subentry_type == "conversation"
        )
        result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_RECOMMENDED: False}
        )
        assert result["step_id"] == "additional"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "model"
        return result


async def test_subentry_location_api_key_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the location lookup of an API key entry which is no longer loaded."""
    result = await _async_reach_subentry_model_step(
        hass,
        mock_config_entry,
        patch("openai.resources.models.AsyncModels.list", new_callable=AsyncMock),
    )

    hass.states.async_set(
        "zone.home", "0", {"latitude": 37.7749, "longitude": -122.4194}
    )
    hass.config.country = "US"
    hass.config.time_zone = "America/Los_Angeles"
    assert hass.states.get("zone.home") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hasattr(mock_config_entry, "runtime_data")

    with (
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_create.return_value = Response(
            object="response",
            id="resp_A",
            created_at=1700000000,
            model="gpt-4o-mini",
            parallel_tool_calls=True,
            tool_choice="auto",
            tools=[],
            output=[
                ResponseOutputMessage(
                    type="message",
                    id="msg_A",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text='{"city": "San Francisco"}',
                            annotations=[],
                        )
                    ],
                    role="assistant",
                    status="completed",
                )
            ],
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
                CONF_WEB_SEARCH_USER_LOCATION: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
