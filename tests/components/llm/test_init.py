"""Tests for the LLM integration."""

from unittest.mock import Mock

import pytest

from homeassistant.components.llm import DATA_PLATFORMS, LLMTools, async_get_tools
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import mock_platform


class _StubTool(llm.Tool):
    """Minimal tool for registry tests."""

    def __init__(self, name: str) -> None:
        """Initialize the stub tool."""
        self.name = name
        self.description = f"{name} description"

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Return an empty result."""
        return {}


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="*",
        assistant="conversation",
        device_id=None,
    )


def _mock_tools_platform(
    hass: HomeAssistant, domain: str, tools: LLMTools | Exception
) -> None:
    """Register a mock <integration>/llm.py platform returning the given tools."""
    if isinstance(tools, Exception):
        async_get_tools = Mock(side_effect=tools)
    else:
        async_get_tools = Mock(return_value=tools)
    hass.config.components.add(domain)
    mock_platform(hass, f"{domain}.llm", Mock(async_get_tools=async_get_tools))


async def test_setup(hass: HomeAssistant) -> None:
    """Test the integration sets up."""
    assert await async_setup_component(hass, "llm", {})
    assert DATA_PLATFORMS in hass.data


async def test_get_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test that tools from an integration platform are returned."""
    tool = _StubTool("my_tool")
    _mock_tools_platform(
        hass, "test", LLMTools(tools=[tool], prompt="use my_tool wisely")
    )

    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context)
    # The llm integration also exposes its own GetDateTime tool (domain "llm").
    assert [tool.name for tool in result.tools] == ["GetDateTime", "my_tool"]
    assert result.prompt == "use my_tool wisely"


async def test_get_tools_empty(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that only the llm integration's own tools are returned by default."""
    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context)
    assert [tool.name for tool in result.tools] == ["GetDateTime"]
    assert result.prompt is None


async def test_get_tools_merges_sorted(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that tools and prompts are merged in a load-order-independent order."""
    tool_a = _StubTool("tool_a")
    tool_b = _StubTool("tool_b")
    # Register "test_b" before "test_a" to prove the result is sorted by domain.
    _mock_tools_platform(hass, "test_b", LLMTools(tools=[tool_b], prompt="prompt b"))
    _mock_tools_platform(hass, "test_a", LLMTools(tools=[tool_a], prompt="prompt a"))

    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context)
    assert [tool.name for tool in result.tools] == ["GetDateTime", "tool_a", "tool_b"]
    assert result.prompt == "prompt a\nprompt b"


async def test_get_tools_isolates_failing_platform(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that one failing platform does not drop the others' tools."""
    tool = _StubTool("good_tool")
    _mock_tools_platform(hass, "test_bad", ValueError("boom"))
    _mock_tools_platform(hass, "test_good", LLMTools(tools=[tool], prompt="prompt"))

    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context)
    assert [tool.name for tool in result.tools] == ["GetDateTime", "good_tool"]
    assert result.prompt == "prompt"
    assert "Error getting tools from LLM platform test_bad" in caplog.text
