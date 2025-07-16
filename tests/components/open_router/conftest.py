"""Fixtures for OpenRouter integration tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest
from python_open_router import ModelsDataWrapper

from homeassistant.components.open_router.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.open_router.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="OpenRouter",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MODEL: "openai/gpt-3.5-turbo"},
                subentry_id="ABCDEF",
                subentry_type="conversation",
                title="GPT-3.5 Turbo",
                unique_id=None,
            )
        ],
    )


@dataclass
class Model:
    """Mock model data."""

    id: str
    name: str


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
async def mock_open_router_client(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
    """Initialize integration."""
    with patch(
        "homeassistant.components.open_router.config_flow.OpenRouterClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        models = await async_load_fixture(hass, "models.json", DOMAIN)
        client.get_models.return_value = ModelsDataWrapper.from_json(models).data
        yield client


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


async def get_generator_from_data[DataT](items: list[DataT]) -> AsyncGenerator[DataT]:
    """Return async generator."""
    for item in items:
        yield item
