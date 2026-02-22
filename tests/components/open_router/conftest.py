"""Fixtures for OpenRouter integration tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest

from homeassistant.components.open_router.const import CONF_PROMPT, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.open_router.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def enable_assist() -> bool:
    """Mock conversation subentry data."""
    return False


@pytest.fixture
def conversation_subentry_data(enable_assist: bool) -> dict[str, Any]:
    """Mock conversation subentry data."""
    res: dict[str, Any] = {
        CONF_NAME: "GPT-3.5 Turbo",
        "chat_model": "openai/gpt-3.5-turbo",
        CONF_PROMPT: "You are a helpful assistant.",
    }
    if enable_assist:
        res[CONF_LLM_HASS_API] = [llm.LLM_API_ASSIST]
    return res


@pytest.fixture
def ai_task_data_subentry_data() -> dict[str, Any]:
    """Mock AI task subentry data."""
    return {
        "chat_model": "openai/gpt-4",
    }


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    conversation_subentry_data: dict[str, Any],
    ai_task_data_subentry_data: dict[str, Any],
) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="OpenRouter",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        subentries_data=[
            ConfigSubentryData(
                data=conversation_subentry_data,
                subentry_id="ABCDEF",
                subentry_type="conversation",
                title="GPT-3.5 Turbo",
                unique_id=None,
            ),
            ConfigSubentryData(
                data=ai_task_data_subentry_data,
                subentry_id="ABCDEG",
                subentry_type="ai_task_data",
                title="GPT-4",
                unique_id=None,
            ),
        ],
    )


@dataclass
class MockModel:
    """Mock model data."""

    id: str
    name: str
    supported_parameters: list[str]


@pytest.fixture
async def mock_openai_client() -> AsyncGenerator[AsyncMock]:
    """Initialize integration."""
    with patch("homeassistant.components.open_router.AsyncOpenAI") as mock_client:
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
                model="gpt-3.5-turbo-0613",
                object="chat.completion",
                system_fingerprint=None,
                usage=CompletionUsage(
                    completion_tokens=9, prompt_tokens=8, total_tokens=17
                ),
            )
        )
        yield client


@pytest.fixture
async def mock_open_router_client(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Initialize integration."""
    with patch(
        "homeassistant.components.open_router.config_flow.OpenRouter",
    ) as mock_client_class:
        client = mock_client_class.return_value

        models_response = MagicMock()
        models_response.data = [
            MockModel(
                id="openai/gpt-3.5-turbo",
                name="OpenAI: GPT-3.5 Turbo",
                supported_parameters=[
                    "max_tokens",
                    "temperature",
                    "top_p",
                    "stop",
                    "frequency_penalty",
                    "presence_penalty",
                    "seed",
                    "logit_bias",
                    "logprobs",
                    "top_logprobs",
                    "response_format",
                ],
            ),
            MockModel(
                id="openai/gpt-4",
                name="OpenAI: GPT-4",
                supported_parameters=[
                    "max_tokens",
                    "temperature",
                    "top_p",
                    "tools",
                    "tool_choice",
                    "stop",
                    "frequency_penalty",
                    "presence_penalty",
                    "seed",
                    "logit_bias",
                    "logprobs",
                    "top_logprobs",
                    "structured_outputs",
                    "response_format",
                ],
            ),
        ]
        client.models.list.return_value = models_response

        api_keys_response = MagicMock()
        client.api_keys.get_current_key_metadata.return_value = api_keys_response

        endpoints_response = MagicMock()
        endpoints_response.data.endpoints = []
        client.endpoints.list.return_value = endpoints_response

        yield client


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


async def get_generator_from_data[DataT](items: list[DataT]) -> AsyncGenerator[DataT]:
    """Return async generator."""
    for item in items:
        yield item
