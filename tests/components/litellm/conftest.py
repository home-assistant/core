"""Fixtures for LiteLLM integration tests."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from openai.types import CompletionUsage, Model
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest

from homeassistant.components.litellm.const import CONF_PROMPT, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_URL = "http://localhost:4000/v1"


async def models_response(*model_ids: str) -> AsyncGenerator[Model]:
    """Yield models as the OpenAI client's `models.list()` would."""
    for model_id in model_ids:
        yield Model(id=model_id, created=0, object="model", owned_by="litellm")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.litellm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def enable_assist() -> bool:
    """Return whether the Assist LLM API is enabled for the conversation agent."""
    return False


@pytest.fixture
def conversation_subentry_data(enable_assist: bool) -> dict[str, Any]:
    """Mock conversation subentry data."""
    res: dict[str, Any] = {
        CONF_MODEL: "gpt-3.5-turbo",
        CONF_PROMPT: "You are a helpful assistant.",
    }
    if enable_assist:
        res[CONF_LLM_HASS_API] = [llm.LLM_API_ASSIST]
    return res


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    conversation_subentry_data: dict[str, Any],
) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="localhost:4000",
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_API_KEY: "bla",
        },
        subentries_data=[
            ConfigSubentryData(
                data=conversation_subentry_data,
                subentry_id="ABCDEF",
                subentry_type="conversation",
                title="gpt-3.5-turbo",
                unique_id=None,
            ),
        ],
    )


@pytest.fixture
async def mock_openai_client() -> AsyncGenerator[AsyncMock]:
    """Mock the OpenAI client used for chat completions."""
    with patch(
        "homeassistant.components.litellm.coordinator.AsyncOpenAI"
    ) as mock_client:
        client = mock_client.return_value
        client.chat.completions.create = AsyncMock(
            return_value=ChatCompletion(
                id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                choices=[
                    Choice(
                        finish_reason="stop",
                        index=0,
                        message=ChatCompletionMessage(
                            content="Hello, how can I help you?",
                            role="assistant",
                            function_call=None,
                            tool_calls=None,
                        ),
                    )
                ],
                created=1700000000,
                model="gpt-3.5-turbo",
                object="chat.completion",
                system_fingerprint=None,
                usage=CompletionUsage(
                    completion_tokens=9, prompt_tokens=8, total_tokens=17
                ),
            )
        )
        yield client


@pytest.fixture
def mock_models() -> Generator[AsyncMock]:
    """Mock the OpenAI client the config flow uses to list proxy models."""
    with patch(
        "homeassistant.components.litellm.config_flow.AsyncOpenAI"
    ) as mock_client:
        client = mock_client.return_value
        client.with_options.return_value.models.list.side_effect = (
            lambda *args, **kwargs: models_response("gpt-3.5-turbo", "gpt-4")
        )
        yield client


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
