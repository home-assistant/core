"""Test the OpenAI Conversation config flow."""

from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError, AuthenticationError, BadRequestError
from openai.types.responses import Response, ResponseOutputMessage, ResponseOutputText
import pytest

from homeassistant import config_entries
from homeassistant.components.openai_conversation.config_flow import RECOMMENDED_OPTIONS
from homeassistant.components.openai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TOP_P,
)
from homeassistant.const import CONF_LLM_HASS_API
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
    assert result2["options"] == RECOMMENDED_OPTIONS
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_recommended(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the options flow with recommended settings."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "recommended": True,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"]["prompt"] == "Speak like a pirate"


async def test_options_unsupported_model(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the options form giving error about models not supported."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert options_flow["type"] == FlowResultType.FORM
    assert options_flow["step_id"] == "init"

    # Configure initial step
    options_flow = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "assist",
        },
    )
    await hass.async_block_till_done()
    assert options_flow["type"] == FlowResultType.FORM
    assert options_flow["step_id"] == "advanced"

    # Configure advanced step
    options_flow = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "o1-mini",
        },
    )
    await hass.async_block_till_done()
    assert options_flow["type"] is FlowResultType.FORM
    assert options_flow["errors"] == {"chat_model": "model_not_supported"}


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


async def test_options_no_model_settings(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test options with no model-specific settings."""
    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    # Configure initial step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    # Configure advanced step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: "gpt-4.5-preview",
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 1.0,
        CONF_CHAT_MODEL: "gpt-4.5-preview",
        CONF_TOP_P: RECOMMENDED_TOP_P,
        CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
    }


async def test_options_reasoning_model(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test options for reasoning models."""
    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    # Configure initial step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    # Configure advanced step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: "o1-pro",
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: 10000,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"

    # Configure model step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_REASONING_EFFORT: "high",
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 1.0,
        CONF_CHAT_MODEL: "o1-pro",
        CONF_TOP_P: RECOMMENDED_TOP_P,
        CONF_MAX_TOKENS: 10000,
        CONF_REASONING_EFFORT: "high",
    }


async def test_options_web_search_no_user_location(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test options for web search without user location."""
    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    # Configure initial step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    # Configure advanced step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"

    # Configure model step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
            CONF_WEB_SEARCH_USER_LOCATION: False,
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 1.0,
        CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
        CONF_TOP_P: RECOMMENDED_TOP_P,
        CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
        CONF_WEB_SEARCH_USER_LOCATION: False,
    }


async def test_options_web_search_user_location(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test fetching user location."""
    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    # Configure initial step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    # Configure advanced step
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 1.0,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"

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
        options = await hass.config_entries.options.async_configure(
            options["flow_id"],
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
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
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
    }


async def test_options_retained(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test that current options are showed as suggested values."""
    # Case 1: web search
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
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
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {
        CONF_PROMPT: "Speak like super Mario",
        CONF_LLM_HASS_API: "none",
        CONF_RECOMMENDED: False,
    }

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like super Mario",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {
        CONF_CHAT_MODEL: "gpt-4o",
        CONF_MAX_TOKENS: 1000,
        CONF_TOP_P: 0.9,
        CONF_TEMPERATURE: 0.8,
    }

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "gpt-4o",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
        CONF_WEB_SEARCH_USER_LOCATION: True,
    }

    # Case 2: reasoning model
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pro",
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "o1-pro",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
            CONF_REASONING_EFFORT: "high",
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {
        CONF_PROMPT: "Speak like a pro",
        CONF_LLM_HASS_API: "none",
        CONF_RECOMMENDED: False,
    }

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pro",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {
        CONF_CHAT_MODEL: "o1-pro",
        CONF_MAX_TOKENS: 1000,
        CONF_TOP_P: 0.9,
        CONF_TEMPERATURE: 0.8,
    }

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "o1-pro",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"
    assert {
        str(key): key.description["suggested_value"]
        for key in options["data_schema"].schema
    } == {CONF_REASONING_EFFORT: "high"}


async def test_options_removed(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test that old options are removed after reconfiguration."""
    # Case 1: web search to recommended
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "assist",
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
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: True,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: True,
        CONF_PROMPT: "Speak like a pirate",
    }

    # Case 2: reasoning to recommended
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "assist",
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "gpt-4o",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
            CONF_REASONING_EFFORT: "high",
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: True,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: True,
        CONF_PROMPT: "Speak like a pirate",
    }

    # Case 3: web search to reasoning
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "assist",
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
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "o3-mini",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_REASONING_EFFORT: "low",
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 0.8,
        CONF_CHAT_MODEL: "o3-mini",
        CONF_TOP_P: 0.9,
        CONF_MAX_TOKENS: 1000,
        CONF_REASONING_EFFORT: "low",
    }

    # Case 4: reasoning to web search
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "assist",
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "o3-mini",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
            CONF_REASONING_EFFORT: "low",
        },
    )

    options = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "init"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: "none",
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "advanced"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_TEMPERATURE: 0.8,
            CONF_CHAT_MODEL: "gpt-4o",
            CONF_TOP_P: 0.9,
            CONF_MAX_TOKENS: 1000,
        },
    )
    assert options["type"] == FlowResultType.FORM
    assert options["step_id"] == "model"

    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
            CONF_WEB_SEARCH_USER_LOCATION: False,
        },
    )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_TEMPERATURE: 0.8,
        CONF_CHAT_MODEL: "gpt-4o",
        CONF_TOP_P: 0.9,
        CONF_MAX_TOKENS: 1000,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
        CONF_WEB_SEARCH_USER_LOCATION: False,
    }
