"""Test the Google Generative AI Conversation config flow."""

from unittest.mock import Mock, patch

import pytest
from requests.exceptions import Timeout

from homeassistant import config_entries
from homeassistant.components.google_generative_ai_conversation.config_flow import (
    RECOMMENDED_OPTIONS,
)
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
    RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CLIENT_ERROR_500, CLIENT_ERROR_API_KEY_INVALID

from tests.common import MockConfigEntry


def get_models_pager():
    """Return a generator that yields the models."""
    model_20_flash = Mock(
        display_name="Gemini 2.0 Flash",
        supported_actions=["generateContent"],
    )
    model_20_flash.name = "models/gemini-2.0-flash"

    model_15_flash = Mock(
        display_name="Gemini 1.5 Flash",
        supported_actions=["generateContent"],
    )
    model_15_flash.name = "models/gemini-1.5-flash-latest"

    model_15_pro = Mock(
        display_name="Gemini 1.5 Pro",
        supported_actions=["generateContent"],
    )
    model_15_pro.name = "models/gemini-1.5-pro-latest"

    model_10_pro = Mock(
        display_name="Gemini 1.0 Pro",
        supported_actions=["generateContent"],
    )
    model_10_pro.name = "models/gemini-pro"

    async def models_pager():
        yield model_20_flash
        yield model_15_flash
        yield model_15_pro
        yield model_10_pro

    return models_pager()


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    # Pretend we already set up a config entry.
    hass.config.components.add("google_generative_ai_conversation")
    MockConfigEntry(
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with (
        patch(
            "google.genai.models.AsyncModels.list",
        ),
        patch(
            "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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


def will_options_be_rendered_again(current_options, new_options) -> bool:
    """Determine if options will be rendered again."""
    return current_options.get(CONF_RECOMMENDED) != new_options.get(CONF_RECOMMENDED)


@pytest.mark.parametrize(
    ("current_options", "new_options", "expected_options", "errors"),
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
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
            },
            None,
        ),
        (
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
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
            None,
        ),
        (
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
            None,
        ),
        (
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_TOP_K: RECOMMENDED_TOP_K,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
                CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
            {CONF_USE_GOOGLE_SEARCH_TOOL: "invalid_google_search_option"},
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
            None,
        ),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_options_switching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    current_options,
    new_options,
    expected_options,
    errors,
) -> None:
    """Test the options form."""
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_entry(
            mock_config_entry, options=current_options
        )
        await hass.async_block_till_done()
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        options_flow = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
    if will_options_be_rendered_again(current_options, new_options):
        retry_options = {
            **current_options,
            CONF_RECOMMENDED: new_options[CONF_RECOMMENDED],
        }
        with patch(
            "google.genai.models.AsyncModels.list",
            return_value=get_models_pager(),
        ):
            options_flow = await hass.config_entries.options.async_configure(
                options_flow["flow_id"],
                retry_options,
            )
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        options = await hass.config_entries.options.async_configure(
            options_flow["flow_id"],
            new_options,
        )
    await hass.async_block_till_done()
    if errors is None:
        assert options["type"] is FlowResultType.CREATE_ENTRY
        assert options["data"] == expected_options

    else:
        assert options["type"] is FlowResultType.FORM
    assert options.get("errors", None) == errors


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            CLIENT_ERROR_500,
            "cannot_connect",
        ),
        (
            Timeout("deadline exceeded"),
            "cannot_connect",
        ),
        (
            CLIENT_ERROR_API_KEY_INVALID,
            "invalid_auth",
        ),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(hass: HomeAssistant, side_effect, error) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("google.genai.models.AsyncModels.list", side_effect=side_effect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bla",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauth flow."""
    hass.config.components.add("google_generative_ai_conversation")
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, state=config_entries.ConfigEntryState.LOADED, title="Gemini"
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["title_placeholders"] == {"name": "Gemini"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api"
    assert "api_key" in result["data_schema"].schema
    assert not result["errors"]

    with (
        patch(
            "google.genai.models.AsyncModels.list",
        ),
        patch(
            "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.google_generative_ai_conversation.async_unload_entry",
            return_value=True,
        ) as mock_unload_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "1234"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {"api_key": "1234"}
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
