"""Tests for the shared LLM DataEntryFlow helpers."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant import data_entry_flow
from homeassistant.components.llm import async_configure_flow_step, format_flow_result
from homeassistant.helpers.llm import ToolResult


def test_format_flow_result_merges_extra_placeholders() -> None:
    """Test step description_placeholders override extra_placeholders."""
    result: data_entry_flow.FlowResult[data_entry_flow.FlowContext, str] = {
        "type": data_entry_flow.FlowResultType.FORM,
        "flow_id": "flow1234",
        "handler": "test",
        "step_id": "confirm",
        "description_placeholders": {"name": "Override"},
    }
    translations = {
        "component.test.fix_flow.step.confirm.title": "{prefix}: {name}",
    }

    formatted = format_flow_result(
        result,
        translations,
        "component.test.fix_flow",
        flow_id="test:1234",
        extra_placeholders={"prefix": "Fix", "name": "Original"},
    )
    assert formatted["title"] == "Fix: Override"


async def test_configure_flow_step_handles_unknown_flow() -> None:
    """Test UnknownFlow from async_configure returns an error ToolResult."""
    flow_mgr = MagicMock()
    flow_mgr.async_configure = AsyncMock(side_effect=data_entry_flow.UnknownFlow)
    flow_handler = MagicMock()
    flow_handler.flow_id = "flow1234"
    flow_handler.cur_step = {"type": data_entry_flow.FlowResultType.FORM}

    result = await async_configure_flow_step(
        flow_mgr,
        flow_handler,
        "test:1234",
        user_input={},
        next_step_id=None,
        abort=False,
    )
    assert result == ToolResult(
        data={"error": "Flow 'test:1234' not found."}, error=True
    )
