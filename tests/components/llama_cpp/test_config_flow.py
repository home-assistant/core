"""Tests for the llama.cpp config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from homeassistant import config_entries
from homeassistant.components.llama_cpp.const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_RECOMMENDED,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_MODEL,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from tests.common import MockConfigEntry

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_CHAT_MODEL: DEFAULT_MODEL,
}


@pytest.fixture(name="mock_setup")
def mock_setup(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Mock the setup of the integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_config_flow(
    hass: HomeAssistant,
    mock_setup: AsyncMock,
) -> None:
    """Test selecting a model in the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "sk-0000000000000000000",
            CONF_BASE_URL: "http://localhost:8080/v1",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://localhost:8080/v1"
    assert result.get("data") == {
        CONF_API_KEY: "sk-0000000000000000000",
        CONF_BASE_URL: "http://localhost:8080/v1",
        CONF_STREAMING: True,
    }
    assert result["options"] == {}
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": {
                **RECOMMENDED_OPTIONS,
                CONF_CHAT_MODEL: "gpt-4",
            },
            "title": "Gpt 4",
            "unique_id": None,
        },
    ]

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (
            openai.APIConnectionError(request=httpx.Request(method="POST", url="test")),
            "cannot_connect",
        ),
        (
            openai.AuthenticationError(
                message="Invalid key",
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="POST", url="test"),
                ),
                body=None,
            ),
            "invalid_auth",
        ),
        (
            openai.OpenAIError("Generic error"),
            "api_error",
        ),
    ],
)
async def test_config_flow_fail_completion(
    hass: HomeAssistant,
    mock_setup: AsyncMock,
    mock_completion: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test config flow where the API completion validation fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "sk-0000000000000000000",
            CONF_BASE_URL: "http://localhost:8080/v1",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    mock_completion.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": expected_error}

    assert len(mock_setup.mock_calls) == 0


async def test_config_flow_no_streaming(
    hass: HomeAssistant,
    mock_setup: AsyncMock,
    mock_completion: AsyncMock,
) -> None:
    """Test config flow where the API does not support streaming."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "sk-0000000000000000000",
            CONF_BASE_URL: "http://localhost:8080/v1",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    def fail_streaming(stream: bool | None = None, **kwargs: Any) -> None:
        """Allow first check to succeed by fail streaming."""
        if stream:
            raise openai.OpenAIError("Invalid request")

    mock_completion.side_effect = fail_streaming

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "http://localhost:8080/v1"
    assert result.get("data") == {
        CONF_API_KEY: "sk-0000000000000000000",
        CONF_BASE_URL: "http://localhost:8080/v1",
        CONF_STREAMING: False,
    }
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": {
                **RECOMMENDED_OPTIONS,
                CONF_CHAT_MODEL: "gpt-4",
            },
            "title": "Gpt 4",
            "unique_id": None,
        },
    ]

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("setup_integration")
async def test_creating_conversation_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        RECOMMENDED_OPTIONS,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Gpt 3.5 Turbo"

    assert result2["data"] == RECOMMENDED_OPTIONS


@pytest.mark.usefixtures("setup_integration")
async def test_creating_conversation_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry when entry is not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        return_value=[],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.usefixtures("setup_integration")
async def test_creating_conversation_subentry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry handles connection errors."""
    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=openai.APIConnectionError(request=None),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("setup_integration")
async def test_creating_conversation_subentry_advanced(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry with custom/advanced settings."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Toggle recommended to False to show advanced options
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_CHAT_MODEL: "gpt-4",
            CONF_PROMPT: "Custom instructions",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "init"

    # Now configure the advanced options
    result3 = await hass.config_entries.subentries.async_configure(
        result2["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_CHAT_MODEL: "gpt-4",
            CONF_PROMPT: "Custom instructions",
            CONF_MAX_TOKENS: 500,
            CONF_TEMPERATURE: 0.5,
            CONF_TOP_P: 0.9,
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Gpt 4"
    assert result3["data"] == {
        CONF_RECOMMENDED: False,
        CONF_CHAT_MODEL: "gpt-4",
        CONF_PROMPT: "Custom instructions",
        CONF_MAX_TOKENS: 500,
        CONF_TEMPERATURE: 0.5,
        CONF_TOP_P: 0.9,
    }


async def test_config_flow_model_selection_fallbacks(
    hass: HomeAssistant,
    mock_setup: AsyncMock,
) -> None:
    """Test model selection fallback options through the config flow."""
    # 1. Test empty list fallback (should fallback to DEFAULT_MODEL)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    async def mock_empty_list(*args, **kwargs):
        return
        yield

    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=mock_empty_list,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost:8080/v1",
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "model"
        schema = result2["data_schema"].schema
        chat_model_key = next(k for k in schema if k == CONF_CHAT_MODEL)
        assert chat_model_key.description["suggested_value"] == DEFAULT_MODEL

    # 2. Test no recommended models match fallback (should select first model in the list)
    result_custom = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    model1 = MagicMock()
    model1.id = "my-custom-model-1"
    model2 = MagicMock()
    model2.id = "my-custom-model-2"

    async def mock_custom_list(*args, **kwargs):
        yield model1
        yield model2

    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=mock_custom_list,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result_custom["flow_id"],
            {
                CONF_BASE_URL: "http://localhost:8080/v1",
            },
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["step_id"] == "model"
        schema = result3["data_schema"].schema
        chat_model_key = next(k for k in schema if k == CONF_CHAT_MODEL)
        assert chat_model_key.description["suggested_value"] == "my-custom-model-1"


async def test_config_flow_connection_errors(
    hass: HomeAssistant,
    mock_setup: AsyncMock,
) -> None:
    """Test config flow handles connection validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # 1. Test AuthenticationError
    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=openai.AuthenticationError(
            message="Invalid Key",
            response=httpx.Response(
                status_code=401,
                request=httpx.Request(method="GET", url="test"),
            ),
            body=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost:8080/v1",
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}

    # 2. Test APIConnectionError
    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=openai.APIConnectionError(
            request=httpx.Request(method="GET", url="test")
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost:8080/v1",
            },
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "cannot_connect"}

    # 3. Test OpenAIError (Generic API errors)
    with patch(
        "homeassistant.components.llama_cpp.config_flow.openai.resources.models.AsyncModels.list",
        side_effect=openai.OpenAIError("generic error"),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost:8080/v1",
            },
        )
        assert result4["type"] is FlowResultType.FORM
        assert result4["errors"] == {"base": "api_error"}


@pytest.mark.usefixtures("setup_integration")
async def test_reconfiguring_conversation_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an existing conversation subentry."""
    subentry = list(mock_config_entry.subentries.values())[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_RECOMMENDED: False,
            CONF_CHAT_MODEL: "gpt-4",
            CONF_PROMPT: "New prompt",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    updated_subentry = list(mock_config_entry.subentries.values())[0]
    assert updated_subentry.title == "Gpt 4"
    assert updated_subentry.data[CONF_CHAT_MODEL] == "gpt-4"
    assert updated_subentry.data[CONF_PROMPT] == "New prompt"
    assert CONF_STREAMING not in updated_subentry.data
