"""Fixtures for LiteLLM integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Choices,
    Message,
    ModelResponse,
)
import pytest

from homeassistant.components.litellm.const import CONF_PROMPT, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_URL = "http://localhost:4000/v1"


def chat_response(
    content: str | None = None,
    tool_calls: list[ChatCompletionMessageToolCall] | None = None,
) -> ModelResponse:
    """Build a litellm completion response."""
    return ModelResponse(
        choices=[
            Choices(
                finish_reason="tool_calls" if tool_calls else "stop",
                index=0,
                message=Message(
                    role="assistant", content=content, tool_calls=tool_calls
                ),
            )
        ],
        model="gpt-3.5-turbo",
    )


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


@pytest.fixture(autouse=True)
def mock_litellm_warmup() -> Generator[MagicMock]:
    """Stub the litellm warm-up completion run during setup.

    The real call spawns a litellm background thread that the strict test
    cleanup flags as lingering; the warm-up only matters at runtime.
    """
    with patch("litellm.completion") as mock_completion:
        yield mock_completion


@pytest.fixture(autouse=True)
def mock_proxy_client() -> Generator[MagicMock]:
    """Mock the LiteLLM proxy client used for model discovery and availability."""
    with patch("homeassistant.components.litellm.coordinator.Client") as mock_client:
        mock_client.return_value.models.list.return_value = [
            {"id": "gpt-3.5-turbo"},
            {"id": "gpt-4"},
        ]
        yield mock_client


@pytest.fixture
def mock_acompletion() -> Generator[AsyncMock]:
    """Mock litellm.acompletion used for chat completions."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=chat_response(content="Hello, how can I help you?"),
    ) as mock_acompletion:
        yield mock_acompletion


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
