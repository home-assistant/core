"""Test the Google Generative AI Conversation config flow."""

from unittest.mock import Mock, patch

from google.api_core.exceptions import ClientError
from google.rpc.error_details_pb2 import ErrorInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


@pytest.fixture
def mock_models():
    """Mock the model list API."""
    model_15_flash = Mock(
        display_name="Gemini 1.5 Flash",
        supported_generation_methods=["generateContent"],
    )
    model_15_flash.name = "models/gemini-1.5-flash-latest"

    model_10_pro = Mock(
        display_name="Gemini 1.0 Pro",
        supported_generation_methods=["generateContent"],
    )
    model_10_pro.name = "models/gemini-pro"
    with patch(
        "homeassistant.components.google_generative_ai_conversation.config_flow.genai.list_models",
        return_value=[model_10_pro],
    ):
        yield


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
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.google_generative_ai_conversation.config_flow.genai.list_models",
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
    assert result2["options"] == {
        CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(
    hass: HomeAssistant, mock_config_entry, mock_init_component, mock_models
) -> None:
    """Test the options form."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "temperature": 0.3,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"]["prompt"] == "Speak like a pirate"
    assert options["data"]["temperature"] == 0.3
    assert options["data"][CONF_CHAT_MODEL] == DEFAULT_CHAT_MODEL
    assert options["data"][CONF_TOP_P] == DEFAULT_TOP_P
    assert options["data"][CONF_TOP_K] == DEFAULT_TOP_K
    assert options["data"][CONF_MAX_TOKENS] == DEFAULT_MAX_TOKENS
    assert (
        CONF_LLM_HASS_API not in options["data"]
    ), "Options flow should not set this key"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            ClientError(message="some error"),
            "cannot_connect",
        ),
        (
            ClientError(
                message="invalid api key",
                error_info=ErrorInfo(reason="API_KEY_INVALID"),
            ),
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

    with patch(
        "homeassistant.components.google_generative_ai_conversation.config_flow.genai.list_models",
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
