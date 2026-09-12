"""Tests for the LLM integration."""

import logging
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.llm import DATA_PLATFORMS, LLMTools, async_get_tools
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import frame, llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import MockUser, mock_platform


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
    hass: HomeAssistant,
    domain: str,
    tools: LLMTools | Exception | None,
    built_in: bool = True,
) -> Mock:
    """Register a mock <integration>/llm.py platform returning the given tools."""
    if isinstance(tools, Exception):
        async_get_tools = Mock(side_effect=tools)
    else:
        async_get_tools = Mock(return_value=tools)
    hass.config.components.add(domain)
    mock_platform(
        hass, f"{domain}.llm", Mock(async_get_tools=async_get_tools), built_in=built_in
    )
    return async_get_tools


async def test_setup(hass: HomeAssistant) -> None:
    """Test the integration sets up."""
    assert await async_setup_component(hass, "llm", {})
    assert DATA_PLATFORMS in hass.data


async def test_get_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test that tools from an integration platform are returned."""
    tool = _StubTool("my_tool")
    platform_get_tools = _mock_tools_platform(
        hass, "test", LLMTools(tools=[tool], prompt="use my_tool wisely")
    )

    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context, "assist")
    # The llm integration also exposes its own llm__GetDateTime tool (domain "llm").
    assert [tool.name for tool in result.tools] == ["llm__GetDateTime", "my_tool"]
    assert result.prompt == "use my_tool wisely"
    platform_get_tools.assert_called_once_with(hass, llm_context, "assist")


async def test_get_tools_empty(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that only the llm integration's own tools are returned by default."""
    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context, "assist")
    assert [tool.name for tool in result.tools] == ["llm__GetDateTime"]
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

    result = await async_get_tools(hass, llm_context, "assist")
    assert [tool.name for tool in result.tools] == [
        "llm__GetDateTime",
        "tool_a",
        "tool_b",
    ]
    assert result.prompt == "prompt a\nprompt b"


async def test_get_tools_skips_none_platform(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that a platform returning None for the API is skipped."""
    tool = _StubTool("good_tool")
    _mock_tools_platform(hass, "test_none", None)
    _mock_tools_platform(hass, "test_good", LLMTools(tools=[tool]))

    assert await async_setup_component(hass, "llm", {})

    result = await async_get_tools(hass, llm_context, "assist")
    assert [tool.name for tool in result.tools] == ["llm__GetDateTime", "good_tool"]
    assert result.prompt is None


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

    result = await async_get_tools(hass, llm_context, "assist")
    assert [tool.name for tool in result.tools] == ["llm__GetDateTime", "good_tool"]
    assert result.prompt == "prompt"
    assert "Error getting tools from LLM platform test_bad" in caplog.text


@pytest.mark.parametrize(
    ("built_in", "expected_level", "expected_type"),
    [(True, logging.ERROR, ""), (False, logging.WARNING, "custom ")],
    ids=["core", "custom"],
)
async def test_get_tools_reports_unprefixed_tool_names(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    caplog: pytest.LogCaptureFixture,
    built_in: bool,
    expected_level: int,
    expected_type: str,
) -> None:
    """Test tools not prefixed with the offering domain are reported."""
    tools = [_StubTool("test__prefixed"), _StubTool("unprefixed")]
    _mock_tools_platform(hass, "test", LLMTools(tools=tools), built_in=built_in)

    assert await async_setup_component(hass, "llm", {})

    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        result = await async_get_tools(hass, llm_context, "assist")

    # The tools are still returned until the requirement starts to fail.
    assert [tool.name for tool in result.tools] == [
        "llm__GetDateTime",
        "test__prefixed",
        "unprefixed",
    ]
    expected_message = (
        f"Detected that {expected_type}integration 'test' provides LLM tools that are "
        "not prefixed with 'test__': unprefixed. This will stop working in Home "
        "Assistant 2027.3"
    )
    record = next(
        record for record in caplog.records if expected_message in record.getMessage()
    )
    assert record.levelno == expected_level


async def test_get_tools_prefixed_tool_names_not_reported(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a platform prefixing all its tools is not reported."""
    _mock_tools_platform(hass, "test", LLMTools(tools=[_StubTool("test__tool")]))

    assert await async_setup_component(hass, "llm", {})

    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        await async_get_tools(hass, llm_context, "assist")

    assert "not prefixed with 'test__'" not in caplog.text


async def test_management_api(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test that ManagementAPI is registered and retrieves management tools for admin."""
    tool = _StubTool("test__mgmt_tool")
    _mock_tools_platform(hass, "test", LLMTools(tools=[tool], prompt="mgmt prompt"))

    assert await async_setup_component(hass, "llm", {})

    apis = {api.id: api for api in llm.async_get_apis(hass)}
    assert llm.LLM_API_ASSIST in apis
    assert llm.LLM_API_MANAGEMENT in apis
    assert apis[llm.LLM_API_MANAGEMENT].name == "Management"

    admin_context = llm.LLMContext(
        platform="test",
        context=Context(user_id=hass_admin_user.id),
        language="*",
        assistant="conversation",
        device_id=None,
    )
    api_instance = await apis[llm.LLM_API_MANAGEMENT].async_get_api_instance(
        admin_context
    )
    assert api_instance.api_prompt == "mgmt prompt"
    assert [t.name for t in api_instance.tools] == [
        "llm__GetDateTime",
        "test__mgmt_tool",
    ]


async def test_management_api_denied_for_non_admin(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test that ManagementAPI raises Unauthorized for non-admin user."""
    tool = _StubTool("test__mgmt_tool")
    _mock_tools_platform(hass, "test", LLMTools(tools=[tool], prompt="mgmt prompt"))

    assert await async_setup_component(hass, "llm", {})

    apis = {api.id: api for api in llm.async_get_apis(hass)}
    non_admin_context = llm.LLMContext(
        platform="test",
        context=Context(user_id=hass_read_only_user.id),
        language="*",
        assistant="conversation",
        device_id=None,
    )
    with pytest.raises(Unauthorized):
        await apis[llm.LLM_API_MANAGEMENT].async_get_api_instance(non_admin_context)


async def test_management_api_denied_without_user(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that ManagementAPI raises Unauthorized when no user is in context."""
    tool = _StubTool("test__mgmt_tool")
    _mock_tools_platform(hass, "test", LLMTools(tools=[tool], prompt="mgmt prompt"))

    assert await async_setup_component(hass, "llm", {})

    apis = {api.id: api for api in llm.async_get_apis(hass)}
    with pytest.raises(Unauthorized):
        await apis[llm.LLM_API_MANAGEMENT].async_get_api_instance(llm_context)
