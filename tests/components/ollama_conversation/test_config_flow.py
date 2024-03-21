"""Test the Ollama Conversation config flow."""

from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant import config_entries
from homeassistant.components import ollama_conversation
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONFIG = {
    ollama_conversation.CONF_URL: "http://localhost:11434",
    ollama_conversation.CONF_MODEL: "test model",
    ollama_conversation.CONF_PROMPT: "test prompt",
    ollama_conversation.CONF_MAX_HISTORY: 2,
    ollama_conversation.CONF_MODEL_OPTIONS: {
        "test option": "test value",
    },
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    # Pretend we already set up a config entry.
    hass.config.components.add(ollama_conversation.DOMAIN)
    MockConfigEntry(
        domain=ollama_conversation.DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        ollama_conversation.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.ollama_conversation.config_flow.ollama.AsyncClient.list",
        ),
        patch(
            "homeassistant.components.ollama_conversation.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == TEST_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the options form."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"], TEST_CONFIG
    )
    await hass.async_block_till_done()
    assert options["type"] == FlowResultType.CREATE_ENTRY
    assert options["data"] == TEST_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message=""), "cannot_connect"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_form_invalid_auth(hass: HomeAssistant, side_effect, error) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        ollama_conversation.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ollama_conversation.config_flow.ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error}
