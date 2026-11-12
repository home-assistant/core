"""Tests for the LLM integration's own tools platform."""

from freezegun import freeze_time
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components import llm as llm_component
from homeassistant.components.llm.llm import GetDateTimeTool
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


def test_get_datetime_equality() -> None:
    """Only the stateless date/time tool opts into equality."""

    class ConfiguredDateTimeTool(GetDateTimeTool):
        """A tool whose subclass may introduce configuration."""

    assert GetDateTimeTool() == GetDateTimeTool()
    assert GetDateTimeTool() != llm.Tool()
    assert GetDateTimeTool() != ConfiguredDateTimeTool()
    assert ConfiguredDateTimeTool() != GetDateTimeTool()
    assert ConfiguredDateTimeTool() != ConfiguredDateTimeTool()


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations for the llm tools platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.config.async_set_time_zone("UTC")
    await hass.async_block_till_done()


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_get_datetime_tool(hass: HomeAssistant) -> None:
    """Test the llm__GetDateTime tool is always offered and returns the current time."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(
        (tool for tool in result.tools if tool.name == "llm__GetDateTime"), None
    )
    assert tool is not None

    with freeze_time("2025-09-17 13:00:00"):
        response = await tool.async_call(
            hass, llm.ToolInput("llm__GetDateTime", {}), llm_context
        )

    assert response == llm.ToolResult(
        data={
            "date": "2025-09-17",
            "time": "13:00:00",
            "timezone": "UTC",
            "weekday": "Wednesday",
        }
    )


@pytest.mark.parametrize(
    "api_ids",
    [
        [llm.LLM_API_ASSIST, llm.LLM_API_HOME_ASSISTANT],
        [llm.LLM_API_HOME_ASSISTANT, llm.LLM_API_ASSIST],
    ],
)
async def test_builtin_apis_merge_without_prefixes(
    hass: HomeAssistant, hass_admin_user: MockUser, api_ids: list[str]
) -> None:
    """Shared built-in tools must compare equal so merging preserves their names."""
    llm_context = _llm_context()
    llm_context.context = Context(user_id=hass_admin_user.id)
    instances = [
        await llm.async_get_api(hass, api_id, llm_context) for api_id in api_ids
    ]
    original_names = {tool.name for instance in instances for tool in instance.tools}
    assert {
        "homeassistant__GetLiveContext",
        "homeassistant__render_template",
        "llm__GetDateTime",
    } <= original_names

    merged = await llm.async_get_api(hass, api_ids, llm_context)

    assert sorted(tool.name for tool in merged.tools) == sorted(original_names)
