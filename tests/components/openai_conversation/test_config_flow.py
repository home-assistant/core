"""Test the OpenAI Conversation config flow."""

from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError, AuthenticationError, BadRequestError
from openai.types.responses import Response, ResponseOutputMessage, ResponseOutputText
import pytest

from homeassistant import config_entries
from homeassistant.components.openai_conversation.config_flow import (
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.components.openai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TOP_P,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
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
    ]
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

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
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


async def test_subentry_unsupported_model(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the subentry form giving error about models not supported."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] == FlowResultType.FORM
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
    assert subentry_flow["type"] == FlowResultType.FORM
    assert subentry_flow["step_id"] == "advanced"

    # Configure advanced step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "o1-mini",
        },
    )
    await hass.async_block_till_done()
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["errors"] == {"chat_model": "model_not_supported"}


async def test_subentry_websearch_unsupported_reasoning_effort(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the subentry form giving error about unsupported minimal reasoning effort."""
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
    assert subentry_flow["step_id"] == "advanced"

    # Configure advanced step
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
            CONF_WEB_SEARCH: True,
        },
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["errors"] == {"web_search": "web_search_minimal_reasoning"}

    # Reconfigure model step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_REASONING_EFFORT: "low",
            CONF_WEB_SEARCH: True,
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
                response=httpx.Response(status_code=None, request=""),
                body=None,
                message=None,
            ),
            "invalid_auth",
        ),
        (
            BadRequestError(
                response=httpx.Response(status_code=None, request=""),
                body=None,
                message=None,
            ),
            "unknown",
        ),
    ],
)
async def test_form_invalid_auth(hass: HomeAssistant, side_effect, error) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.resources.models.AsyncModels.list",
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


@pytest.mark.parametrize(
    ("current_options", "new_options", "expected_options"),
    [
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
                CONF_REASONING_EFFORT: "high",
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
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
                },
                {
                    CONF_WEB_SEARCH: True,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
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
                CONF_VERBOSITY: "high",
                CONF_CODE_INTERPRETER: False,
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
            },
            (
                {
                    CONF_RECOMMENDED: False,
                    CONF_PROMPT: "Speak like a pirate",
                },
                {
                    CONF_TEMPERATURE: 0.8,
                    CONF_CHAT_MODEL: "gpt-5",
                    CONF_TOP_P: 0.9,
                    CONF_MAX_TOKENS: 1000,
                },
                {
                    CONF_REASONING_EFFORT: "minimal",
                    CONF_CODE_INTERPRETER: False,
                    CONF_VERBOSITY: "high",
                    CONF_WEB_SEARCH: False,
                    CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                    CONF_WEB_SEARCH_USER_LOCATION: False,
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "minimal",
                CONF_CODE_INTERPRETER: False,
                CONF_VERBOSITY: "high",
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: False,
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_CITY: "San Francisco",
                CONF_WEB_SEARCH_REGION: "California",
                CONF_WEB_SEARCH_COUNTRY: "US",
                CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
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
                CONF_REASONING_EFFORT: "low",
                CONF_CODE_INTERPRETER: True,
            },
        ),
        (  # Case 4: reasoning to web search
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_REASONING_EFFORT: "low",
                CONF_CODE_INTERPRETER: True,
                CONF_VERBOSITY: "medium",
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
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
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
                CONF_CODE_INTERPRETER: True,
                CONF_VERBOSITY: "medium",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
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
                },
            ),
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.8,
                CONF_CHAT_MODEL: "gpt-5-pro",
                CONF_TOP_P: 0.9,
                CONF_MAX_TOKENS: 1000,
                CONF_VERBOSITY: "medium",
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
                CONF_WEB_SEARCH_USER_LOCATION: False,
            },
        ),
    ],
)
async def test_subentry_switching(
    hass: HomeAssistant,
    mock_config_entry,
    mock_init_component,
    current_options,
    new_options,
    expected_options,
) -> None:
    """Test the subentry form."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=current_options
    )
    await hass.async_block_till_done()
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["step_id"] == "init"

    for step_options in new_options:
        assert subentry_flow["type"] == FlowResultType.FORM

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


async def test_subentry_web_search_user_location(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test fetching user location."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] == FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    # Configure initial step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
        },
    )
    assert subentry_flow["type"] == FlowResultType.FORM
    assert subentry_flow["step_id"] == "advanced"

    # Configure advanced step
    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        },
    )
    await hass.async_block_till_done()
    assert subentry_flow["type"] == FlowResultType.FORM
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
    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 1.0,
        CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
        CONF_TOP_P: RECOMMENDED_TOP_P,
        CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
        CONF_WEB_SEARCH_USER_LOCATION: True,
        CONF_WEB_SEARCH_CITY: "San Francisco",
        CONF_WEB_SEARCH_REGION: "California",
        CONF_WEB_SEARCH_COUNTRY: "US",
        CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        CONF_CODE_INTERPRETER: False,
    }


async def test_creating_ai_task_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating an AI task subentry."""
    old_subentries = set(mock_config_entry.subentries)
    # Original conversation + original ai_task
    assert len(mock_config_entry.subentries) == 2

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
        len(mock_config_entry.subentries) == 3
    )  # Original conversation + original ai_task + new ai_task

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


async def test_creating_ai_task_subentry_advanced(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating an AI task subentry with advanced settings."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Go to advanced settings
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Advanced AI Task",
            CONF_RECOMMENDED: False,
        },
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "advanced"

    # Configure advanced settings
    result3 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4o",
            CONF_MAX_TOKENS: 200,
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
        },
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "Advanced AI Task"
    assert result4.get("data") == {
        CONF_RECOMMENDED: False,
        CONF_CHAT_MODEL: "gpt-4o",
        CONF_IMAGE_MODEL: "gpt-image-1",
        CONF_MAX_TOKENS: 200,
        CONF_TEMPERATURE: 0.5,
        CONF_TOP_P: 0.9,
        CONF_CODE_INTERPRETER: False,
    }
