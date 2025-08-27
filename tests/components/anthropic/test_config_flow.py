"""Test the Anthropic config flow."""

from unittest.mock import AsyncMock, Mock, patch

from anthropic import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
)
from httpx import URL, Request, Response
import pytest

from homeassistant import config_entries
from homeassistant.components.anthropic.config_flow import RECOMMENDED_OPTIONS
from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_MAX_USES,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_THINKING_BUDGET,
    RECOMMENDED_WEB_SEARCH_MAX_USES,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    # Pretend we already set up a config entry.
    hass.config.components.add("anthropic")
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
            "homeassistant.components.anthropic.config_flow.anthropic.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.anthropic.async_setup_entry",
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
            "data": RECOMMENDED_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        }
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
        "anthropic.resources.models.AsyncModels.retrieve",
        return_value=Mock(display_name="Claude 3.5 Sonnet"),
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
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test creating a conversation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_options"
    assert not result["errors"]

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Mock name", **RECOMMENDED_OPTIONS},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Mock name"

    processed_options = RECOMMENDED_OPTIONS.copy()
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
        "anthropic.resources.models.AsyncModels.list",
        return_value=[],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_options_thinking_budget_more_than_max(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test error about thinking budget being more than max tokens."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "max_tokens": 8192,
            "chat_model": "claude-3-7-sonnet-latest",
            "temperature": 1,
            "thinking_budget": 16384,
            "recommended": False,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.FORM
    assert options["errors"] == {"thinking_budget": "thinking_budget_too_large"}


async def test_subentry_web_search_unsupported_model(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test error when enabling web search with unsupported model."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "You are helpful",
            "max_tokens": 8192,
            "chat_model": "claude-3-haiku-20240307",  # Unsupported for web search
            "temperature": 1,
            "thinking_budget": 0,
            "recommended": False,
            "web_search": True,
            "web_search_max_uses": 5,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.FORM
    assert options["errors"] == {"web_search": "web_search_unsupported_model"}


async def test_subentry_web_search_supported_model(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test web search configuration works with supported model."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "You are helpful",
            "max_tokens": 8192,
            "chat_model": "claude-3-5-sonnet-latest",  # Supported for web search
            "temperature": 1,
            "thinking_budget": 0,
            "recommended": False,
            "web_search": True,
            "web_search_max_uses": 10,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_WEB_SEARCH] is True
    assert subentry.data[CONF_WEB_SEARCH_MAX_USES] == 10


async def test_subentry_web_search_disabled(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test web search configuration when disabled."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    options = await hass.config_entries.subentries.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "You are helpful",
            "max_tokens": 8192,
            "chat_model": "claude-3-haiku-20240307",  # Unsupported for web search
            "temperature": 1,
            "thinking_budget": 0,
            "recommended": False,
            "web_search": False,  # Disabled
            "web_search_max_uses": 5,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_WEB_SEARCH] is False
    assert subentry.data[CONF_WEB_SEARCH_MAX_USES] == 5


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "cannot_connect"),
        (APITimeoutError(request=None), "timeout_connect"),
        (
            BadRequestError(
                message="Your credit balance is too low to access the Claude API. Please go to Plans & Billing to upgrade or purchase credits.",
                response=Response(
                    status_code=400,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "invalid_request_error"}},
            ),
            "unknown",
        ),
        (
            AuthenticationError(
                message="invalid x-api-key",
                response=Response(
                    status_code=401,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "authentication_error"}},
            ),
            "authentication_error",
        ),
        (
            InternalServerError(
                message=None,
                response=Response(
                    status_code=500,
                    request=Request(method="POST", url=URL()),
                ),
                body=None,
            ),
            "unknown",
        ),
        (
            APIResponseValidationError(
                response=Response(
                    status_code=200,
                    request=Request(method="POST", url=URL()),
                ),
                body=None,
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
        "homeassistant.components.anthropic.config_flow.anthropic.resources.models.AsyncModels.list",
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


@pytest.mark.parametrize(
    ("current_options", "new_options", "expected_options"),
    [
        (
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "bla",
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_LLM_HASS_API: [],
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_THINKING_BUDGET: RECOMMENDED_THINKING_BUDGET,
                CONF_WEB_SEARCH: False,
                CONF_WEB_SEARCH_MAX_USES: 5.0,
            },
        ),
        (
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_THINKING_BUDGET: RECOMMENDED_THINKING_BUDGET,
            },
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
                CONF_PROMPT: "",
            },
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
                CONF_PROMPT: "",
            },
        ),
        (
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "",
                CONF_LLM_HASS_API: "assist",
            },
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "",
                CONF_LLM_HASS_API: ["assist"],
            },
            {
                CONF_RECOMMENDED: True,
                CONF_PROMPT: "",
                CONF_LLM_HASS_API: ["assist"],
            },
        ),
    ],
)
async def test_subentry_options_switching(
    hass: HomeAssistant,
    mock_config_entry,
    mock_init_component,
    current_options,
    new_options,
    expected_options,
) -> None:
    """Test the subentry options form."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=current_options
    )
    await hass.async_block_till_done()

    options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    if current_options.get(CONF_RECOMMENDED) != new_options.get(CONF_RECOMMENDED):
        options_flow = await hass.config_entries.subentries.async_configure(
            options_flow["flow_id"],
            {
                **current_options,
                CONF_RECOMMENDED: new_options[CONF_RECOMMENDED],
            },
        )
    options = await hass.config_entries.subentries.async_configure(
        options_flow["flow_id"],
        new_options,
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data == expected_options
