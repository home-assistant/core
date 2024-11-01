"""Test the OpenAI Conversation config flow."""

from unittest.mock import patch

from httpx import Response
from openai import APIConnectionError, AuthenticationError, BadRequestError
import pytest

from homeassistant import config_entries
from homeassistant.components.openai_conversation.config_flow import RECOMMENDED_OPTIONS
from homeassistant.components.openai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
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


async def test_options(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the options form."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            "prompt": "Speak like a pirate",
            "max_tokens": 200,
        },
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"]["prompt"] == "Speak like a pirate"
    assert options["data"]["max_tokens"] == 200
    assert options["data"][CONF_CHAT_MODEL] == RECOMMENDED_CHAT_MODEL


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "cannot_connect"),
        (
            AuthenticationError(
                response=Response(status_code=None, request=""), body=None, message=None
            ),
            "invalid_auth",
        ),
        (
            BadRequestError(
                response=Response(status_code=None, request=""), body=None, message=None
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
        (
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: "none",
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
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            },
        ),
        (
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_TEMPERATURE: 0.3,
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
                CONF_TOP_P: RECOMMENDED_TOP_P,
                CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            },
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: "assist",
                CONF_PROMPT: "",
            },
            {
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: "assist",
                CONF_PROMPT: "",
            },
        ),
    ],
)
async def test_options_switching(
    hass: HomeAssistant,
    mock_config_entry,
    mock_init_component,
    current_options,
    new_options,
    expected_options,
) -> None:
    """Test the options form."""
    hass.config_entries.async_update_entry(mock_config_entry, options=current_options)
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    if current_options.get(CONF_RECOMMENDED) != new_options.get(CONF_RECOMMENDED):
        options_flow = await hass.config_entries.options.async_configure(
            options_flow["flow_id"],
            {
                **current_options,
                CONF_RECOMMENDED: new_options[CONF_RECOMMENDED],
            },
        )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        new_options,
    )
    await hass.async_block_till_done()
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert options["data"] == expected_options
