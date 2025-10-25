"""Test the Google Generative AI Conversation config flow."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import Timeout

from homeassistant import config_entries
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
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import API_ERROR_500, CLIENT_ERROR_API_KEY_INVALID

from tests.common import MockConfigEntry


def get_models_pager():
    """Return a generator that yields the models."""
    model_25_flash = Mock(
        supported_actions=["generateContent"],
    )
    model_25_flash.name = "models/gemini-2.5-flash"

    model_20_flash = Mock(
        supported_actions=["generateContent"],
    )
    model_20_flash.name = "models/gemini-2.0-flash"

    model_15_flash = Mock(
        supported_actions=["generateContent"],
    )
    model_15_flash.name = "models/gemini-1.5-flash-latest"

    model_15_pro = Mock(
        supported_actions=["generateContent"],
    )
    model_15_pro.name = "models/gemini-1.5-pro-latest"

    model_25_flash_tts = Mock(
        supported_actions=["generateContent"],
    )
    model_25_flash_tts.name = "models/gemini-2.5-flash-preview-tts"

    async def models_pager():
        yield model_25_flash
        yield model_20_flash
        yield model_15_flash
        yield model_15_pro
        yield model_25_flash_tts

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
    assert result2["options"] == {}
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": RECOMMENDED_CONVERSATION_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "tts",
            "data": RECOMMENDED_TTS_OPTIONS,
            "title": DEFAULT_TTS_NAME,
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
    ]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
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
        result["flow_id"],
        {
            CONF_API_KEY: "bla",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("subentry_type", "options"),
    [
        ("conversation", RECOMMENDED_CONVERSATION_OPTIONS),
        ("stt", RECOMMENDED_STT_OPTIONS),
        ("tts", RECOMMENDED_TTS_OPTIONS),
        ("ai_task_data", RECOMMENDED_AI_TASK_OPTIONS),
    ],
)
async def test_creating_subentry(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
    options: dict[str, Any],
) -> None:
    """Test creating a subentry."""
    old_subentries = set(mock_config_entry.subentries)

    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, subentry_type),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == "set_options"
    assert not result["errors"]

    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            result["data_schema"]({CONF_NAME: "Mock name", **options}),
        )
        await hass.async_block_till_done()

    expected_options = options.copy()
    if CONF_PROMPT in expected_options:
        expected_options[CONF_PROMPT] = expected_options[CONF_PROMPT].strip()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Mock name"
    assert result2["data"] == expected_options

    assert len(mock_config_entry.subentries) == len(old_subentries) + 1

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]

    assert new_subentry.subentry_type == subentry_type
    assert new_subentry.data == expected_options
    assert new_subentry.title == "Mock name"


@pytest.mark.parametrize(
    ("subentry_type", "recommended_model", "options"),
    [
        (
            "conversation",
            RECOMMENDED_CHAT_MODEL,
            {
                CONF_PROMPT: "You are Mario",
                CONF_LLM_HASS_API: ["assist"],
                CONF_RECOMMENDED: False,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TEMPERATURE: 1.0,
                CONF_TOP_P: 1.0,
                CONF_TOP_K: 1,
                CONF_MAX_TOKENS: 1024,
                CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_HATE_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_USE_GOOGLE_SEARCH_TOOL: RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
            },
        ),
        (
            "stt",
            RECOMMENDED_STT_MODEL,
            {
                CONF_PROMPT: "Transcribe this",
                CONF_RECOMMENDED: False,
                CONF_CHAT_MODEL: RECOMMENDED_STT_MODEL,
                CONF_TEMPERATURE: 1.0,
                CONF_TOP_P: 1.0,
                CONF_TOP_K: 1,
                CONF_MAX_TOKENS: 1024,
                CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_HATE_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
            },
        ),
        (
            "tts",
            RECOMMENDED_TTS_MODEL,
            {
                CONF_RECOMMENDED: False,
                CONF_CHAT_MODEL: RECOMMENDED_TTS_MODEL,
                CONF_TEMPERATURE: 1.0,
                CONF_TOP_P: 1.0,
                CONF_TOP_K: 1,
                CONF_MAX_TOKENS: 1024,
                CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_HATE_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
            },
        ),
        (
            "ai_task_data",
            RECOMMENDED_CHAT_MODEL,
            {
                CONF_RECOMMENDED: False,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TEMPERATURE: 1.0,
                CONF_TOP_P: 1.0,
                CONF_TOP_K: 1,
                CONF_MAX_TOKENS: 1024,
                CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_HATE_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
                CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
            },
        ),
    ],
)
async def test_creating_subentry_custom_options(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
    recommended_model: str,
    options: dict[str, Any],
) -> None:
    """Test creating a subentry with custom options."""
    old_subentries = set(mock_config_entry.subentries)

    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, subentry_type),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == "set_options"
    assert not result["errors"]

    # Uncheck recommended to show custom options
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            result["data_schema"]({CONF_RECOMMENDED: False}),
        )
    assert result2["type"] is FlowResultType.FORM

    # Find the schema key for CONF_CHAT_MODEL and check its default
    schema_dict = result2["data_schema"].schema
    chat_model_key = next(key for key in schema_dict if key.schema == CONF_CHAT_MODEL)
    assert chat_model_key.default() == recommended_model
    models_in_selector = [
        opt["value"] for opt in schema_dict[chat_model_key].config["options"]
    ]
    assert recommended_model in models_in_selector

    # Submit the form
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result3 = await hass.config_entries.subentries.async_configure(
            result2["flow_id"],
            result2["data_schema"]({CONF_NAME: "Mock name", **options}),
        )
        await hass.async_block_till_done()

    expected_options = options.copy()
    if CONF_PROMPT in expected_options:
        expected_options[CONF_PROMPT] = expected_options[CONF_PROMPT].strip()
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Mock name"
    assert result3["data"] == expected_options

    assert len(mock_config_entry.subentries) == len(old_subentries) + 1

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]

    assert new_subentry.subentry_type == subentry_type
    assert new_subentry.data == expected_options
    assert new_subentry.title == "Mock name"


async def test_creating_conversation_subentry_not_loaded(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that subentry fails to init if entry not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


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
async def test_subentry_options_switching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    current_options,
    new_options,
    expected_options,
    errors,
) -> None:
    """Test the options form."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_subentry(
            mock_config_entry, subentry, data=current_options
        )
        await hass.async_block_till_done()
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
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
            options_flow = await hass.config_entries.subentries.async_configure(
                options_flow["flow_id"],
                retry_options,
            )
    with patch(
        "google.genai.models.AsyncModels.list",
        return_value=get_models_pager(),
    ):
        options = await hass.config_entries.subentries.async_configure(
            options_flow["flow_id"],
            new_options,
        )
        await hass.async_block_till_done()
    if errors is None:
        assert options["type"] is FlowResultType.ABORT
        assert options["reason"] == "reconfigure_successful"
        assert subentry.data == expected_options

    else:
        assert options["type"] is FlowResultType.FORM
    assert options.get("errors", None) == errors


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            API_ERROR_500,
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
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
        title="Gemini",
        version=2,
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
